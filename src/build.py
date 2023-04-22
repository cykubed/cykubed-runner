import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

from httpx import AsyncClient
from wcmatch import glob

from common.enums import AgentEventType, TestRunStatus
from common.exceptions import BuildFailedException, FilestoreReadError
from common.fsclient import AsyncFSClient
from common.redisutils import async_redis
from common.schemas import NewTestRun, AgentBuildStarted, AgentCompletedBuildMessage
from common.settings import settings
from common.utils import utcnow
from logs import logger
from utils import runcmd, set_status, get_testrun, get_git_sha

INCLUDE_SPEC_REGEX = re.compile(r'specPattern:\s*[\"\'](.*)[\"\']')
EXCLUDE_SPEC_REGEX = re.compile(r'excludeSpecPattern:\s*[\"\'](.*)[\"\']')


def clone_repos(testrun: NewTestRun):
    logger.info("Cloning repository")
    builddir = settings.get_build_dir()
    if os.path.exists(builddir):
        # this is just for when we're running locally during development
        shutil.rmtree(builddir)
    os.makedirs(settings.get_build_dir(), exist_ok=True)
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
    builddir = settings.get_build_dir()
    branch = testrun.branch

    logger.info(f"Creating build distribution for branch \"{branch}\" in dir {builddir}")
    os.chdir(builddir)
    lockhash = get_lock_hash(builddir)

    logger.info(f"Checking node_modules cache for {lockhash}.tar.lz4")

    rebuild = True
    fname = f'{lockhash}.tar.lz4'
    if await fs.exists(fname):
        try:
            logger.info("Node cache hit: fetch and unpack")
            await fs.download_and_untar(fname, builddir)
            rebuild = False
        except FilestoreReadError:
            rebuild = True

    if rebuild:
        # build node_modules
        env = dict(CYPRESS_INSTALL_BINARY='0')
        if settings.NODE_PATH:
            env['PATH'] = settings.NODE_PATH+':'+os.environ['PATH']
        if os.path.exists('yarn.lock'):
            logger.info("Building new node cache using yarn")
            runcmd(f'yarn install --pure-lockfile --cache_folder={settings.get_yarn_cache_dir()}', cmd=True, env=env)
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


async def build_app(testrun: NewTestRun):
    logger.info('Building app')
    wdir = os.path.join(settings.SCRATCH_DIR, 'build')

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
    filepath = os.path.join(settings.get_temp_dir(), filename)
    # tarball everything bar the cached stuff
    runcmd(f'tar cf {filepath} --exclude="node_modules" --exclude="cypress_cache" --exclude=".git" . -I lz4', cwd=wdir)
    return filepath


async def run(trid: int, httpclient: AsyncClient):
    logger.info(f'Starting build for testrun {trid}')

    r = await httpclient.post('/build-started',
                              content=AgentBuildStarted(started=utcnow()).json())
    if not r.status_code == 200:
        raise BuildFailedException(f"Failed to contact main server: {r.status_code}: {r.text}")

    fs = AsyncFSClient()

    try:
        await fs.connect()
        await clone_and_build(trid, fs, httpclient)
    finally:
        await fs.close()


async def set_build_details(testrun: NewTestRun, specs: list[str]) -> NewTestRun | None:
    r = async_redis()
    await r.sadd(f'testrun:{testrun.id}:specs', *specs)
    testrun.status = TestRunStatus.running
    await r.set(f'testrun:{testrun.id}', testrun.json())
    # tell the agent so it can inform the main server and then start the runner job
    await r.rpush('messages', AgentCompletedBuildMessage(type=AgentEventType.build_completed,
                                                         testrun_id=testrun.id,
                                                         finished=utcnow(),
                                                         sha=testrun.sha, specs=specs).json())


async def clone_and_build(trid: int, fs: AsyncFSClient, httpclient: AsyncClient):
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

    await set_status(httpclient, TestRunStatus.building)

    # clone
    wdir = settings.get_build_dir()
    clone_repos(testrun)
    if not testrun.sha:
        testrun.sha = get_git_sha(testrun)

    # determine the specs
    specs = get_specs(wdir)
    if not specs:
        logger.info("No specs - nothing to test")
        await set_status(httpclient, TestRunStatus.passed)
        return

    logger.info(f"Found {len(specs)} spec files")

    testrun_dist = f'{testrun.sha}.tar.lz4'
    logger.debug(f"Checking cache for distribution for SHA {testrun.sha}")

    if await fs.exists(testrun_dist):
        logger.info(f"Cache hit")
        testrun.cache_key = get_lock_hash(settings.get_build_dir())
    else:
        logger.info(f"Cache miss - build app")
        # install node environment (or fetch from cache)
        lockhash, upload_node_env = await create_node_environment(fs, testrun)
        # build the app
        build_path = await build_app(testrun)
        cache_filename = f'{lockhash}.tar.lz4'
        if upload_node_env:
            # tar up and store
            tarfile = os.path.join(settings.get_temp_dir(), cache_filename)
            logger.info(f'Tarring node_modules cache')
            runcmd(f'tar cf {tarfile} -I lz4 node_modules cypress_cache')
            # upload to cache
            logger.info(f'Uploading cache')
            await fs.upload(tarfile)
            logger.info(f'Cache uploaded')

        await fs.upload(build_path)
        logger.info("Distribution uploaded")

        t = time.time() - t
        logger.info(f"Distribution created in {t:.1f}s")

    await set_build_details(testrun, specs)
