import hashlib
import json
import os
import re
import time

from wcmatch import glob

from common.enums import AgentEventType, TestRunStatus
from common.exceptions import BuildFailedException
from common.redisutils import sync_redis
from common.schemas import NewTestRun, BuildCompletedAgentMessage, AgentTestRun, \
    CloneCompletedAgentMessage
from logs import logger
from settings import settings
from utils import runcmd, get_testrun, get_git_sha

INCLUDE_SPEC_REGEX = re.compile(r'specPattern:\s*[\"\'](.*)[\"\']')
EXCLUDE_SPEC_REGEX = re.compile(r'excludeSpecPattern:\s*[\"\'](.*)[\"\']')


def clone_repos(testrun: NewTestRun):
    logger.info("Cloning repository")
    builddir = settings.BUILD_DIR
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


def create_node_environment():
    """
    Create node environment from either Yarn or npm
    """

    logger.info(f"Creating node distribution")

    t = time.time()
    env = dict(CYPRESS_INSTALL_BINARY='0')
    if os.path.exists('yarn.lock'):
        logger.info("Building new node cache using yarn")
        runcmd(f'yarn install --pure-lockfile --cache_folder={settings.get_yarn_cache_dir()}',
               cmd=True, env=env, cwd=settings.NODE_CACHE_DIR)
    else:
        logger.info("Building new node cache using npm")
        runcmd('npm ci', cmd=True, env=env, cwd=settings.NODE_CACHE_DIR)
    # install Cypress binary
    os.chdir(settings.BUILD_DIR)
    os.mkdir('cypress_cache')
    logger.info("Installing Cypress binary")
    runcmd('cypress install')
    t = time.time() - t
    logger.info(f"Created node environment in {t:.1f}s")


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


def clone(trid: int):
    tstart = time.time()
    testrun = get_testrun(trid)
    if not testrun:
        raise BuildFailedException("No such testrun")

    logger.init(testrun.id, source="builder")

    testrun.status = TestRunStatus.building

    clone_repos(testrun)

    if not testrun.sha:
        testrun.sha = get_git_sha(testrun)

    # determine the specs
    specs = get_specs(settings.BUILD_DIR)
    r = sync_redis()
    if specs:
        logger.info(f"Found {len(specs)} spec files")
        atr = AgentTestRun(specs=specs, cache_key=get_lock_hash(settings.BUILD_DIR), **testrun.dict())
        r.sadd(f'testrun:{testrun.id}:specs', *specs)
        testrun.status = TestRunStatus.running
        r.set(f'testrun:{testrun.id}', atr.json())
    # tell the agent
    r.rpush('messages', CloneCompletedAgentMessage(type=AgentEventType.clone_completed,
                                                   testrun_id=testrun.id,
                                                   duration=time.time() - tstart).json())


def build(trid: int):
    """
    Build the distribution
    """
    tstart = time.time()

    testrun = get_testrun(trid)
    if not testrun:
        raise BuildFailedException("No such testrun")
    if testrun.status != 'building':
        raise BuildFailedException(f"Testrun is in {testrun.status} state")

    logger.init(testrun.id, source="builder")

    logger.info(f'Build distribution for test run {testrun.local_id}')

    node_modules = os.path.join(settings.NODE_CACHE_DIR, 'node_modules')
    if os.path.exists(node_modules):
        logger.info('Using cached node environment')
    else:
        create_node_environment()

    # build the app
    build_app(testrun)

    # tell the agent so it can inform the main server and then start the runner job
    sync_redis().rpush('messages', BuildCompletedAgentMessage(type=AgentEventType.build_completed,
                                                              testrun_id=testrun.id,
                                                              duration=time.time()-tstart).json())


def build_app(testrun: AgentTestRun):
    logger.info('Building app')

    wdir = settings.BUILD_DIR

    os.symlink(f'{settings.NODE_CACHE_DIR}/node_modules', f'{wdir}/node_modules')
    # build the app
    runcmd(testrun.project.build_cmd, cmd=True, cwd=wdir)

    # check for dist and index file
    distdir = os.path.join(wdir, 'dist')

    if not os.path.exists(distdir):
        raise BuildFailedException("No dist directory: please check your build command")

    if not os.path.exists(os.path.join(distdir, 'index.html')):
        raise BuildFailedException("Could not find index.html file in dist directory")
