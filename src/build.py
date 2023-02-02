import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

import httpx
from wcmatch import glob

from common.exceptions import BuildFailedException
from common.schemas import NewTestRun, TestRunDetail, CompletedBuild
from common.settings import settings
from common.utils import get_headers
from cypress import fetch_from_cache, BuildFailed
from logs import logger
from utils import runcmd, upload_to_cache

INCLUDE_SPEC_REGEX = re.compile(r'specPattern:\s*[\"\'](.*)[\"\']')
EXCLUDE_SPEC_REGEX = re.compile(r'excludeSpecPattern:\s*[\"\'](.*)[\"\']')


def clone_repos(testrun: NewTestRun) -> str:
    logger.info("Cloning repository")
    builddir = tempfile.mkdtemp()
    os.chdir(builddir)
    if not testrun.sha:
        runcmd(f'git clone --single-branch --depth 1 --recursive --branch {testrun.branch} {testrun.project.url} {builddir}',
               log=True)
    else:
        runcmd(f'git clone --recursive {testrun.project.url} {builddir}', log=True)

    logger.info(f"Cloned branch {testrun.branch}")
    if testrun.sha:
        runcmd(f'git reset --hard {testrun.sha}', cwd=builddir)
    return builddir


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


def create_node_environment(testrun: NewTestRun, builddir: str) -> str:
    """
    Build the app. Uses a cache for node_modules
    """
    branch = testrun.branch

    logger.info(f"Creating build distribution for branch \"{branch}\" in dir {builddir}")
    os.chdir(builddir)
    lockhash = get_lock_hash(builddir)

    cache_filename = f'{lockhash}.tar.lz4'
    url = os.path.join(settings.CACHE_URL, cache_filename)
    logger.debug(f"Checking node_modules cache for {url}")

    rebuild = True

    resp = httpx.head(url)
    if resp.status_code == 200:
        try:
            logger.info("Node cache hit: fetch and unpack")
            fetch_from_cache(lockhash, builddir)
            rebuild = False
        except BuildFailed:
            # unpack
            logger.error('Failed to unpack cached distribution: rebuilding it')
            shutil.rmtree('node_modules')
            shutil.rmtree('cypress_cache')
            rebuild = True

    if rebuild:
        # build node_modules
        if os.path.exists('yarn.lock'):
            logger.info("Building new node cache using yarn")
            runcmd('yarn install --pure-lockfile', cmd=True, env=dict(CYPRESS_INSTALL_BINARY='0'))
        else:
            logger.info("Building new node cache using npm")
            runcmd('npm ci', cmd=True, env=dict(CYPRESS_INSTALL_BINARY='0'))
        # install Cypress binary
        os.mkdir('cypress_cache')
        logger.info("Installing Cypress binary")
        runcmd('cypress install')
        # tar up and store
        tarfile = f'/tmp/{cache_filename}'
        logger.info(f'Uploading node_modules cache')
        runcmd(f'tar cf {tarfile} -I lz4 node_modules cypress_cache')
        # upload to cache
        upload_to_cache(tarfile, cache_filename)
        logger.info(f'Cache uploaded')
        os.remove(tarfile)
    return lockhash


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


def build_app(testrun: NewTestRun, wdir: str):
    logger.info('Building app')

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
    filename = f'{testrun.project.id}-{testrun.local_id}.tar.lz4'
    filepath = os.path.join('/tmp', filename)
    # tarball everything bar the cached stuff
    runcmd(f'tar cf {filepath} --exclude="node_modules cypress_cache" . -I lz4', cwd=wdir)
    # upload to cache
    upload_to_cache(filepath, filename)


def post_status(project_id: int, local_id: int, status: str):
    resp = httpx.put(f'{settings.MAIN_API_URL}/agent/testrun/{project_id}/{local_id}/status/{status}',
                     headers=get_headers())
    if resp.status_code != 200:
        raise BuildFailedException(f"Failed to update status for run {local_id}: bailing out")


def clone_and_build(project_id: int, local_id: int):
    """
    Clone and build
    """
    logger.info(f'** Clone and build distribution for test run {local_id} **')

    r = httpx.get(f'{settings.MAIN_API_URL}/testrun/{project_id}/{local_id}', headers=get_headers())
    if r.status_code != 200:
        logger.warning("Failed to fetch test run config - quitting")
        raise BuildFailedException(f"Failed to fetch testrun {local_id} status: {r.text}")

    testrun = NewTestRun.parse_obj(r.json())
    t = time.time()

    post_status(project_id, local_id, 'building')

    # clone
    wdir = clone_repos(testrun)
    if not testrun.sha:
        testrun.sha = subprocess.check_output(['git', 'rev-parse', testrun.branch], cwd=wdir,
                                              text=True).strip('\n')

    # install node packages first (or fetch from cache)
    lockhash = create_node_environment(testrun, wdir)

    # now we can determine the specs
    specs = get_specs(wdir)

    # tell cykube
    r = httpx.put(f'{settings.MAIN_API_URL}/agent/testrun/{project_id}/{testrun.local_id}/specs',
                  headers=get_headers(),
                  json={'specs': specs, 'sha': testrun.sha})
    if r.status_code != 200:
        raise BuildFailedException(f"Failed to update cykube with list of specs - bailing out: {r.text}")
    testrun = TestRunDetail.parse_obj(r.json())

    if not specs:
        logger.info("No specs - nothing to test")
        post_status(project_id, local_id, 'passed')
        return

    logger.info(f"Found {len(specs)} spec files")
    build_app(testrun, wdir)

    completed_build = CompletedBuild(testrun=testrun, cache_hash=lockhash)
    try:
        r = httpx.post(f'{settings.AGENT_URL}/build-complete', data=completed_build.json())
        if r.status_code != 200:
            raise BuildFailedException(f"Failed to update complete build - bailing out: {r.text}")
    except Exception as ex:
        raise BuildFailedException(f"Failed to update complete build: {ex}")
    t = time.time() - t
    logger.info(f"Distribution created in {t:.1f}s")

