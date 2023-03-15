import hashlib
import json
import os
import re
import shutil
import subprocess
import time

from wcmatch import glob

from common.db import get_testrun, send_status_message, set_build_details
from common.exceptions import BuildFailedException
from common.fsclient import AsyncFSClient
from common.schemas import NewTestRun
from common.settings import settings
from cypress import fetch_from_cache
from logs import logger
from utils import runcmd

INCLUDE_SPEC_REGEX = re.compile(r'specPattern:\s*[\"\'](.*)[\"\']')
EXCLUDE_SPEC_REGEX = re.compile(r'excludeSpecPattern:\s*[\"\'](.*)[\"\']')


def clone_repos(testrun: NewTestRun):
    logger.info("Cloning repository")
    builddir = settings.BUILD_DIR
    if os.path.exists(builddir):
        # this is just for when we're running locally during development
        shutil.rmtree(builddir)
    os.makedirs(settings.BUILD_DIR)
    if not testrun.sha:
        runcmd(f'git clone --single-branch --depth 1 --recursive --branch {testrun.branch} {testrun.url} {builddir}',
               log=True)
    else:
        runcmd(f'git clone --recursive {testrun.url} {builddir}', log=True)

    logger.info(f"Cloned branch {testrun.branch}")
    if testrun.sha:
        runcmd(f'git reset --hard {testrun.sha}', cwd=builddir)


def get_lock_hash(build_dir):
    m = hashlib.sha256()
    lockfile = os.path.join(build_dir, 'package-lock.json')
    if not os.path.exists(lockfile):
        lockfile = os.path.join(build_dir, 'yarn.lock')

    if not os.path.exists(lockfile):
        raise BuildFailedException("No lock file")

    # hash the lock
    with open(lockfile, 'rb') as f:
        m.update(f.read())
    return m.hexdigest()


async def create_node_environment(fs: AsyncFSClient, testrun: NewTestRun) -> tuple[str, bool]:
    """
    Build the app. Uses a cache for node_modules
    Returns (cache_hash, was_rebuilt)
    """
    builddir = settings.BUILD_DIR
    branch = testrun.branch

    logger.info(f"Creating build distribution for branch \"{branch}\" in dir {builddir}")
    os.chdir(builddir)
    lockhash = get_lock_hash(builddir)

    logger.info(f"Checking node_modules cache for {lockhash}")

    rebuild = True
    if await fs.exists(lockhash):
        try:
            logger.info("Node cache hit: fetch and unpack")
            fetch_from_cache(lockhash)
            rebuild = False
        except BuildFailedException:
            # unpack
            logger.error('Failed to unpack cached distribution: rebuilding it')
            shutil.rmtree('node_modules')
            shutil.rmtree('cypress_cache')
            rebuild = True

    if rebuild:
        # build node_modules
        env = dict(CYPRESS_INSTALL_BINARY='0')
        if settings.NODE_PATH:
            env['PATH'] = settings.NODE_PATH+':'+os.environ['PATH']
        if os.path.exists('yarn.lock'):
            logger.info("Building new node cache using yarn")
            runcmd('yarn install --pure-lockfile', cmd=True, env=env)
        else:
            logger.info("Building new node cache using npm")
            runcmd('npm ci', cmd=True, env=env)
        # install Cypress binary
        os.mkdir('cypress_cache')
        logger.info("Installing Cypress binary")
        runcmd('cypress install')
    testrun.cache_key = lockhash
    return lockhash, rebuild


def make_array(x):
    if not type(x) is list:
        return [x]
    return x


def get_specs(wdir):
    cyjson = os.path.join(wdir, 'cypress.json')

    if os.path.exists(cyjson):
        with open(cyjson, 'r') as f:
            config = json.loads(f.read())
        folder = config.get('integrationFolder', 'cypress/integration')
        include_globs = make_array(config.get('testFiles', '**/*.*'))
        exclude_globs = make_array(config.get('ignoreTestFiles', '*.hot-update.js'))
    else:
        # technically I should use node to extract the various globs, but it's more trouble than it's worth
        # so i'll stick with regex
        folder = ""
        config = os.path.join(wdir, 'cypress.config.js')
        if not os.path.exists(config):
            config = os.path.join(wdir, 'cypress.config.ts')
            if not os.path.exists(config):
                raise BuildFailedException("Cannot find Cypress config file")
        with open(config, 'r') as f:
            cfgtext = f.read()
            include_globs = re.findall(INCLUDE_SPEC_REGEX, cfgtext)
            exclude_globs = re.findall(EXCLUDE_SPEC_REGEX, cfgtext)

    specs = glob.glob(include_globs, root_dir=os.path.join(wdir, folder),
                      flags=glob.BRACE, exclude=exclude_globs)

    specs = [os.path.join(folder, s) for s in specs]
    return specs


async def build_app(fs: AsyncFSClient, testrun: NewTestRun):
    logger.info('Building app')
    wdir = settings.BUILD_DIR

    # build the app
    runcmd(testrun.project.build_cmd, cmd=True)

    # check for dist and index file
    distdir = os.path.join(wdir, 'dist')

    if not os.path.exists(distdir):
        raise BuildFailedException("No dist directory: please check your build command")

    if not os.path.exists(os.path.join(distdir, 'index.html')):
        raise BuildFailedException("Could not find index.html file in dist directory")

    # tar it up
    logger.info("Upload distribution")
    filename = f'{testrun.sha}.tar.lz4'
    filepath = os.path.join('/tmp', filename)
    # tarball everything bar the cached stuff
    runcmd(f'tar cf {filepath} --exclude="node_modules" --exclude="cypress_cache" --exclude=".git" . -I lz4', cwd=wdir)
    # upload to cache
    await fs.upload(filepath)
    logger.info("Distribution uploaded")


async def clone_and_build(trid: int):
    """
    Clone and build. Using async just to reuse the libraries
    """

    testrun = await get_testrun(trid)
    if not testrun:
        raise BuildFailedException("No such testrun")
    if testrun.status != 'started':
        raise BuildFailedException(f"Testrun is in {testrun.status} state")

    logger.init(testrun.id, source="builder")

    logger.info(f'** Clone and build distribution for test run {testrun.local_id} **')

    t = time.time()

    send_status_message(testrun.id, 'building')

    # clone
    wdir = settings.BUILD_DIR
    clone_repos(testrun)
    if not testrun.sha:
        testrun.sha = subprocess.check_output(['git', 'rev-parse', testrun.branch], cwd=wdir,
                                              text=True).strip('\n')

    # install node packages first (or fetch from cache)
    fs = AsyncFSClient()
    lockhash, upload = await create_node_environment(fs, testrun)

    # now we can determine the specs
    specs = get_specs(wdir)

    if not specs:
        logger.info("No specs - nothing to test")
        send_status_message(testrun.id, 'passed')
        return

    logger.info(f"Found {len(specs)} spec files")

    logger.debug(f"Checking cache for distribution for SHA {testrun.sha}")

    if await fs.exists(testrun.sha):
        logger.info(f"Cache hit")
    else:
        await build_app(fs, testrun)

    if upload:
        cache_filename = f'{lockhash}.tar.lz4'
        # tar up and store
        tarfile = f'/tmp/{cache_filename}'
        logger.info(f'Uploading node_modules cache')
        runcmd(f'tar cf {tarfile} -I lz4 node_modules cypress_cache')
        # upload to cache
        await fs.upload(tarfile)
        logger.info(f'Cache uploaded')

    await set_build_details(testrun, specs)
    t = time.time() - t
    logger.info(f"Distribution created in {t:.1f}s")

