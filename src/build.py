import hashlib
import json
import os
import re
import subprocess
import tempfile
import time

import httpx
from loguru import logger
from wcmatch import glob

from common.exceptions import BuildFailedException
from common.schemas import NewTestRun, TestRunDetail, CompletedBuild
from common.utils import get_headers
from settings import settings
from utils import runcmd, upload_to_cache

INCLUDE_SPEC_REGEX = re.compile(r'specPattern:\s*[\"\'](.*)[\"\']')
EXCLUDE_SPEC_REGEX = re.compile(r'excludeSpecPattern:\s*[\"\'](.*)[\"\']')


def clone_repos(url: str, branch: str) -> str:
    logger.info("Cloning repository")
    builddir = tempfile.mkdtemp()
    os.chdir(builddir)
    runcmd(f'git clone --single-branch --depth 1 --recursive --branch {branch} {url} {builddir}')
    logger.info(f"Cloned branch {branch}")
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
    logger.info(f"Checking node_modules cache for {url}")

    with httpx.stream('GET', url) as resp:
        if resp.status_code == 200:
            # unpack
            logger.info("Node cache hit: fetch and unpack")
            with tempfile.NamedTemporaryFile(suffix='.tar.lz4') as fdst:
                for chunk in resp.iter_raw():
                    fdst.write(chunk)
                runcmd(f'tar xf {fdst.name} -I lz4')
        else:
            # build node_modules
            if os.path.exists('yarn.lock'):
                logger.info("Building new node cache using yarn")
                runcmd('yarn install --pure-lockfile')
            else:
                logger.info("Building new node cache using npm")
                runcmd('npm ci')

            # tar up and store
            tarfile = f'/tmp/{cache_filename}'
            runcmd(f'tar cf {tarfile} -I lz4 node_modules cypress_cache')
            # upload to cache
            logger.info(f'Uploading node_modules cache')
            upload_to_cache(tarfile)
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
    # build the app
    env = os.environ.copy()
    env['PATH'] = './node_modules/.bin:' + env['PATH']
    env['CYPRESS_CACHE_FOLDER'] = os.path.join(wdir, 'cypress_cache')
    result = subprocess.run(testrun.project.build_cmd, shell=True, capture_output=True, env=env,
                            encoding='utf8', cwd=wdir)
    if result.returncode:
        raise BuildFailedException("Failed:\n"+result.stderr)

    # tar it up
    logger.info("Create distribution and cleanup")
    filename = f'/tmp/{testrun.id}.tar.lz4'
    # tarball everything bar the cached stuff
    runcmd(f'tar cf {filename} --exclude="node_modules cypress_cache" . -I lz4', cwd=wdir)
    # upload to cache
    upload_to_cache(filename)


def post_status(testrun_id: int, status: str):
    resp = httpx.put(f'{settings.MAIN_API_URL}/agent/testrun/{testrun_id}/status/{status}', headers=get_headers())
    if resp.status_code != 200:
        raise BuildFailedException(f"Failed to update status for run {testrun_id}: bailing out")


def clone_and_build(testrun_id: int):
    """
    Clone and build
    """
    logger.info(f'** Clone and build distribution for test run {testrun_id} **')

    r = httpx.get(f'{settings.MAIN_API_URL}/testrun/{testrun_id}', headers=get_headers())
    if r.status_code != 200:
        logger.warning("Failed to fetch test run config - quitting")
        raise BuildFailedException(f"Failed to fetch testrun {testrun_id} status: {r.text}")

    testrun = NewTestRun.parse_obj(r.json())
    t = time.time()

    post_status(testrun_id, 'building')

    # clone
    wdir = clone_repos(testrun.project.url, testrun.branch)
    if not testrun.sha:
        testrun.sha = subprocess.check_output(['git', 'rev-parse', testrun.branch], cwd=wdir,
                                              text=True).strip('\n')

    # install node packages first (or fetch from cache)
    lockhash = create_node_environment(testrun, wdir)

    # now we can determine the specs
    specs = get_specs(wdir)

    # tell cykube
    r = httpx.put(f'{settings.MAIN_API_URL}/agent/testrun/{testrun.id}/specs', headers=get_headers(),
                             json={'specs': specs, 'sha': testrun.sha})
    if r.status_code != 200:
        raise BuildFailedException(f"Failed to update cykube with list of specs - bailing out: {r.text}")
    testrun = TestRunDetail.parse_obj(r.json())

    if not specs:
        logger.info("No specs - nothing to test")
        post_status(testrun_id, 'passed')
        return

    logger.info(f"Found {len(specs)} spec files: building the app")
    build_app(testrun, wdir)

    completed_build = CompletedBuild(testrun=testrun, cache_hash=lockhash)
    r = httpx.post(f'{settings.AGENT_URL}/build-complete', data=completed_build.json())
    if r.status_code != 200:
        raise BuildFailedException(f"Failed to update complete build - bailing out: {r.text}")
    t = time.time() - t
    logger.info(f"Distribution created in {t:.1f}s")

