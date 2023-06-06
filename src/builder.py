import json
import os
import re
import time

from wcmatch import glob

from common.enums import TestRunStatus, AgentEventType
from common.exceptions import BuildFailedException
from common.schemas import NewTestRun, \
    AgentBuildCompletedEvent, AgentEvent
from settings import settings
from utils import runcmd, get_testrun, send_agent_event, logger, increase_duration

INCLUDE_SPEC_REGEX = re.compile(r'specPattern:\s*[\"\'](.*)[\"\']')
EXCLUDE_SPEC_REGEX = re.compile(r'excludeSpecPattern:\s*[\"\'](.*)[\"\']')


def clone_repos(testrun: NewTestRun):
    logger.info("Cloning repository")
    if not testrun.sha:
        runcmd(f'git clone --single-branch --depth 1 --recursive --branch {testrun.branch} {testrun.url} .',
               log=True, cwd=settings.src_dir)
    else:
        runcmd(f'git clone --recursive {testrun.url} .', log=True, cwd=settings.src_dir)

    logger.info(f"Cloned branch {testrun.branch}")
    if testrun.sha:
        runcmd(f'git reset --hard {testrun.sha}', cwd=settings.src_dir)


def create_node_environment():
    """
    Create node environment from either Yarn or npm
    """

    logger.info(f"Creating node distribution")

    t = time.time()

    if os.path.exists(os.path.join(settings.src_dir, 'yarn.lock')):
        logger.info("Building new node cache using yarn")
        runcmd(f'yarn install --pure-lockfile --cache_folder={settings.get_yarn_cache_dir()}',
               cmd=True, cwd=settings.src_dir)
    else:
        logger.info("Building new node cache using npm")
        runcmd('npm ci', cmd=True, cwd=settings.src_dir)

    t = time.time() - t
    logger.info(f"Created node environment in {t:.1f}s")

    # pre-verify it so it's properly read-only
    runcmd('cypress verify', cwd=settings.src_dir, cmd=True)


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


def build(trid: int):
    """
    Build the distribution
    """
    tstart = time.time()

    try:
        testrun = get_testrun(trid)
        testrun.status = TestRunStatus.building

        if not testrun:
            raise BuildFailedException("No such testrun")

        logger.init(testrun.id, source="builder")

        clone_repos(testrun)

        logger.info(f'Build distribution for test run {testrun.local_id}')

        cached_node_modules = os.path.join(settings.BUILD_DIR, 'node_modules')
        if not os.path.exists(cached_node_modules):
            # no cache - create node environment
            create_node_environment()
        else:
            logger.info('Using cached environment')
            runcmd(f'mv {cached_node_modules} {settings.src_dir}')

        # build the app
        build_app(testrun)

        # set the duration
        increase_duration(testrun.id, 'build', int(time.time() - tstart))

        # tell the agent so it can inform the main server and then start the runner job
        send_agent_event(AgentBuildCompletedEvent(
            testrun_id=testrun.id,
            specs=get_specs(settings.src_dir),
            duration=time.time() - tstart))
    except Exception as ex:
        increase_duration(trid, 'build', int(time.time() - tstart))
        raise ex


def prepare_cache(trid):
    """
    Move the cachable stuff into root and delete the rest
    """
    runcmd(f'mv {settings.src_dir}/node_modules {settings.BUILD_DIR}')
    runcmd(f'rm -fr {settings.src_dir}')
    send_agent_event(AgentEvent(testrun_id=trid, type=AgentEventType.cache_prepared))


def build_app(testrun: NewTestRun):
    logger.info('Building app')

    # build the app
    runcmd(testrun.project.build_cmd, cmd=True, cwd=settings.src_dir)

    # check for dist and index file
    distdir = os.path.join(settings.src_dir, 'dist')

    if not os.path.exists(distdir):
        raise BuildFailedException("No dist directory: please check your build command")

    if not os.path.exists(os.path.join(distdir, 'index.html')):
        raise BuildFailedException("Could not find index.html file in dist directory")

