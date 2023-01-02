import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

import httpx
from httpx import AsyncClient
from loguru import logger
from wcmatch import glob

from common.exceptions import BuildFailedException
from common.schemas import NewTestRun, TestRunDetail
from jobs import create_runner_jobs
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


async def create_node_environment(testrun: NewTestRun, builddir: str):
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
    async with AsyncClient().stream('GET', url) as resp:
        if resp.status_code == 200:
            # unpack
            logger.info("Node cache hit: fetch and unpack")
            with tempfile.NamedTemporaryFile(suffix='.tar.lz4') as fdst:
                async for chunk in resp.aiter_bytes():
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
            runcmd(f'tar cf {tarfile} -I lz4 node_modules')
            # upload to cache
            logger.info(f'Uploading node_modules cache')
            await upload_to_cache(tarfile)
            logger.info(f'Cache uploaded')
            os.remove(tarfile)


def make_array(x):
    if not type(x) is list:
        return [x]
    return x


def get_specs(wdir):
    cyjson = os.path.join(wdir, 'cypress.json')

    tscdir = None

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

    if tscdir:
        shutil.rmtree(tscdir)

    specs = [os.path.join(folder, s) for s in specs]
    return specs


async def build_app(testrun: NewTestRun, wdir: str):
    # build the app
    runcmd(f'{testrun.project.build_cmd}', cwd=wdir)

    # tar it up
    logger.info("Create distribution and cleanup")
    filename = f'/tmp/{testrun.sha}.tar.lz4'
    # tarball everything
    runcmd(f'tar cf {filename} . -I lz4', cwd=wdir)
    # upload to cache
    await upload_to_cache(filename)


def post_status(testrun_id: int, status: str):
    resp = httpx.put(f'{settings.AGENT_URL}/testrun/{testrun_id}/status/{status}')
    if resp.status_code != 200:
        raise BuildFailedException(f"Failed to update status for run {testrun_id}: bailing out")


async def clone_and_build(testrun_id: int):
    """
    Clone and build
    """
    logger.info(f'** Clone and build distribution for test run {testrun_id} **')

    r = httpx.get(f'{settings.AGENT_URL}/testrun/{testrun_id}')
    if r.status_code != 200:
        logger.warning("Failed to fetch test run config from agent - quitting")
        raise BuildFailedException(f"Failed to fetch testrun {testrun_id} status")

    testrun = NewTestRun.parse_obj(r.json())
    t = time.time()

    post_status(testrun_id, 'building')

    # clone
    wdir = clone_repos(testrun.project.url, testrun.branch)
    if not testrun.sha:
        testrun.sha = subprocess.check_output(['git', 'rev-parse', testrun.branch], cwd=wdir,
                                              text=True).strip('\n')

    # install node packages first (or fetch from cache)
    await create_node_environment(testrun, wdir)

    # now we can determine the specs
    specs = get_specs(wdir)

    # tell the agent
    r = httpx.put(f'{settings.AGENT_URL}/testrun/{testrun.id}/specs',
                             json={'specs': specs, 'sha': testrun.sha})
    if r.status_code != 200:
        raise BuildFailedException(f"Failed to update agent with list of specs - bailing out: {r.text}")
    testrun = TestRunDetail.parse_obj(r.json())

    if not specs:
        logger.info("No specs - nothing to test")
        post_status(testrun_id, 'passed')
        return

    # start the runner jobs - that way the cluster has a head start on spinning
    # up new nodes
    logger.info(f"Starting {testrun.project.parallelism} Jobs")
    create_runner_jobs(testrun)

    logger.info(f"Found {len(specs)} spec files: building the app")
    await build_app(testrun, wdir)

    # now we can run
    post_status(testrun_id, 'running')
    t = time.time() - t
    logger.info(f"Distribution created in {t:.1f}s")

