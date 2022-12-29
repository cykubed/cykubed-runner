import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
from shutil import copyfileobj

from httpx import AsyncClient
from wcmatch import glob

from common.exceptions import BuildFailedException
from common.schemas import NewTestRun
from settings import settings
from utils import runcmd, upload_to_cache

INCLUDE_SPEC_REGEX = re.compile(r'specPattern:\s*[\"\'](.*)[\"\']')
EXCLUDE_SPEC_REGEX = re.compile(r'excludeSpecPattern:\s*[\"\'](.*)[\"\']')


def clone_repos(url: str, branch: str) -> str:
    logging.info("Cloning repository")
    builddir = tempfile.mkdtemp()
    os.chdir(builddir)
    runcmd(f'git clone --single-branch --depth 1 --recursive --branch {branch} {url} {builddir}')
    logging.info(f"Cloned branch {branch}")
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


async def create_node_environment(testrun: NewTestRun, builddir: str, http: AsyncClient):
    """
    Build the app. Uses a cache for node_modules
    """
    branch = testrun.branch

    logging.info(f"Creating build distribution for branch {branch} in dir {builddir}")
    os.chdir(builddir)
    lockhash = get_lock_hash(builddir)

    cache_filename = f'{lockhash}.tar.lz4'
    async with http.stream(os.path.join(settings.CACHE_URL, cache_filename)) as resp:
        if resp.status_code == 200:
            with tempfile.NamedTemporaryFile() as fdst:
                copyfileobj(resp.raw, fdst)
                # unpack
                logging.info("Fetching npm cache")
                runcmd(f'tar xf {fdst.name} -I lz4')
        else:
            # build node_modules
            if os.path.exists('yarn.lock'):
                logging.info("Building new node cache using yarn")
                runcmd('yarn install --pure-lockfile')
            else:
                logging.info("Building new node cache using npm")
                runcmd('npm ci')

            # tar up and store
            tarfile = f'/tmp/{cache_filename}'
            runcmd(f'tar cf {tarfile} -I lz4 node_modules')
            # upload to cache
            await upload_to_cache(http, tarfile)
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

