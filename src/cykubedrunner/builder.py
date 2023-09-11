import json
import os
import re
import time
from wcmatch import glob
import yaml

from cykubedrunner.common.enums import TestRunStatus, AgentEventType
from cykubedrunner.common.exceptions import BuildFailedException
from cykubedrunner.common.schemas import NewTestRun, \
    AgentBuildCompletedEvent, AgentEvent
from cykubedrunner.app import app
from cykubedrunner.settings import settings
from cykubedrunner.utils import runcmd, get_testrun, send_agent_event, logger, root_file_exists

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


def enable_yarn2_global_cache(yarnrc):
    with open(yarnrc) as f:
        data = yaml.safe_load(f)
        data['enableGlobalCache'] = True
        data['globalFolder'] = settings.yarn2_global_cache
    with open(yarnrc, 'w') as f:
        yaml.dump(data, f)


def create_node_environment():
    """
    Create node environment from either Yarn or npm
    """

    logger.info(f"Creating node distribution")

    t = time.time()
    using_cache = False

    if root_file_exists('yarn.lock'):
        logger.info("Building new node cache using yarn")
        # check for yarn2
        app.is_yarn = True
        yarnrc = os.path.join(settings.src_dir, '.yarnrc.yml')
        if os.path.exists(yarnrc):
            logger.info("Found a .yarnrc.yml: assume Yarn2")
            runcmd('yarn set version berry', cmd=True, cwd=settings.src_dir)

            # yarn2 - is this a zero-install?
            if os.path.exists(os.path.join(settings.src_dir, '.yarn', 'cache')):
                logger.info("Found .yarn/cache: assume zero-install")
                app.is_yarn_zero_install = True
            else:
                logger.info("No .yarn/cache found: set to use global cache")
                if os.path.exists(settings.yarn2_global_cache):
                    using_cache = True
                enable_yarn2_global_cache(yarnrc)

            runcmd(f'yarn install', cmd=True, cwd=settings.src_dir)
        else:
            logger.info("Assume Yarn1.x")
            if os.path.exists(settings.cached_node_modules):
                logger.info("Using cached node_modules")
                using_cache = True
                runcmd(f'mv {settings.cached_node_modules} {settings.src_dir}')
            else:
                runcmd(f'yarn install --pure-lockfile --cache-folder={settings.BUILD_DIR}/.yarn-cache',
                       cmd=True, cwd=settings.src_dir)
    else:
        if os.path.exists(settings.cached_node_modules):
            logger.info("Using cached node_modules")
            using_cache = True
            runcmd(f'mv {settings.cached_node_modules} {settings.src_dir}')
        else:
            logger.info("Building new node cache using npm")
            runcmd('npm ci', cmd=True, cwd=settings.src_dir)

    t = time.time() - t
    logger.info(f"Created node environment in {t:.1f}s")

    # pre-verify it so it's properly read-only
    if not using_cache:
        runcmd('cypress verify', cwd=settings.src_dir, cmd=True, node=True)


def make_array(x):
    if not type(x) is list:
        return [x]
    return x


def get_specs(wdir, filter_regex=None):
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
    if filter_regex:
        specs = [s for s in specs if re.search(filter_regex, s)]
    return specs


def build(trid: int):
    """
    Build the distribution
    """
    tstart = time.time()

    testrun = get_testrun(trid)
    testrun.status = TestRunStatus.building

    if not testrun:
        raise BuildFailedException("No such testrun")

    logger.init(testrun.id, source="builder")

    clone_repos(testrun)

    if root_file_exists('yarn.lock'):
        app.is_yarn = True
        if root_file_exists('.yarnc.yml'):
            app.is_yarn_modern = True

    logger.info(f'Build distribution for test run {testrun.local_id}')

    # create node environment
    create_node_environment()

    # build the app
    build_app(testrun)

    # tell the agent so it can inform the main server and then start the runner job
    send_agent_event(AgentBuildCompletedEvent(
        testrun_id=testrun.id,
        specs=get_specs(settings.src_dir, testrun.project.spec_filter),
        duration=time.time() - tstart))


def prepare_cache(trid):
    """
    Move the cachable stuff into root and delete the rest
    """

    if os.path.exists(f'{settings.src_dir}/node_modules') and not app.is_yarn_modern:
        runcmd(f'mv {settings.src_dir}/node_modules {settings.BUILD_DIR}')

    runcmd(f'rm -fr {settings.src_dir}')
    logger.info("Send cache_prepared event")
    send_agent_event(AgentEvent(testrun_id=trid, type=AgentEventType.cache_prepared))


def build_app(testrun: NewTestRun):
    logger.info('Building app')

    # build the app
    runcmd(testrun.project.build_cmd, cmd=True, cwd=settings.src_dir, node=True)

    # check for dist and index file
    distdir = os.path.join(settings.src_dir, 'dist')

    if not os.path.exists(distdir):
        raise BuildFailedException("No dist directory: please check your build command")

    if not os.path.exists(os.path.join(distdir, 'index.html')):
        raise BuildFailedException("Could not find index.html file in dist directory")

