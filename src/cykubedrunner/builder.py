import json
import os
import re
import time

import yaml
from wcmatch import glob

from cykubedrunner.app import app
from cykubedrunner.common.enums import TestRunStatus, TestFramework
from cykubedrunner.common.exceptions import BuildFailedException
from cykubedrunner.common.schemas import NewTestRun, \
    AgentBuildCompleted
from cykubedrunner.settings import settings
from cykubedrunner.utils import runcmd, logger, root_file_exists, get_node_version

CYPRESS_INCLUDE_SPEC_REGEX = re.compile(r'specPattern:\s*[\"\'](.*)[\"\']')
CYPRESS_EXCLUDE_SPEC_REGEX = re.compile(r'excludeSpecPattern:\s*[\"\'](.*)[\"\']')

PLAYWRIGHT_TESTDIR_REGEX = re.compile(r'testDir:\s*[\"\'](.*)[\"\']')
PLAYWRIGHT_INCLUDE_SPEC_REGEX = re.compile(r'testMatch:\s*[\"\'](.*)[\"\']')
PLAYWRIGHT_EXCLUDE_SPEC_REGEX = re.compile(r'testIgnore:\s*[\"\'](.*)[\"\']')


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


def create_node_environment(testrun: NewTestRun):
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
    if testrun.project.test_framework == TestFramework.cypress:
        if not using_cache:
            runcmd('cypress verify', cwd=settings.src_dir, cmd=True, node=True)
    else:
        # check we have the browsers
        runcmd('npx playwright install', cwd=settings.src_dir, cmd=True,
               env=dict(PLAYWRIGHT_BROWSERS_PATH='0'))



def make_array(x):
    if not type(x) is list:
        return [x]
    return x


def get_playwright_specs(wdir, spec_filter=None):
    """
    Parse the list of specs from the config files. At the moment this relies on regex rather than reading
    the config file natively. I acknowledge that this is an imperfect solution and could break if the config
    file has actual code in it: a better solution is probably a tiny Node library to do the same job.
    """
    config = os.path.join(wdir, 'playwright.config.js')
    if not os.path.exists(config):
        config = os.path.join(wdir, 'playwright.config.ts')
        if not os.path.exists(config):
            raise BuildFailedException("Cannot find Playwright config file")

    with open(config, 'r') as f:
        cfgtext = f.read()
        testdir = re.findall(PLAYWRIGHT_TESTDIR_REGEX, cfgtext)
        if testdir:
            testdir = os.path.normpath(testdir[0])
        else:
            testdir = wdir
        rootdir = os.path.abspath(os.path.join(wdir, testdir))

        if not spec_filter:
            include_globs = re.findall(PLAYWRIGHT_INCLUDE_SPEC_REGEX, cfgtext)
            exclude_globs = re.findall(PLAYWRIGHT_EXCLUDE_SPEC_REGEX, cfgtext)
            if not include_globs:
                include_globs = ["**/*.@(spec|test).?(c|m)[jt]s?(x)"]

    return [os.path.join(testdir, x) for x in glob.glob(include_globs, root_dir=rootdir, flags=glob.BRACE,
                     exclude=exclude_globs)]


def get_cypress_specs(wdir, spec_filter=None):
    cyjson = os.path.join(wdir, 'cypress.json')
    folder = wdir
    prefix = None
    if spec_filter:
        include_globs = spec_filter
        exclude_globs = None
    else:
        if os.path.exists(cyjson):
            with open(cyjson, 'r') as f:
                config = json.loads(f.read())
            prefix = config.get('integrationFolder', 'cypress/integration')
            folder = os.path.join(wdir, prefix)
            include_globs = make_array(config.get('testFiles', '**/*.*'))
            exclude_globs = make_array(config.get('ignoreTestFiles', '*.hot-update.js'))
        else:
            # technically I should use node to extract the various globs, but it's more trouble than it's worth
            # so i'll stick with regex
            config = os.path.join(wdir, 'cypress.config.js')
            if not os.path.exists(config):
                config = os.path.join(wdir, 'cypress.config.ts')
                if not os.path.exists(config):
                    raise BuildFailedException("Cannot find Cypress config file")
            with open(config, 'r') as f:
                cfgtext = f.read()
                include_globs = re.findall(CYPRESS_INCLUDE_SPEC_REGEX, cfgtext)
                exclude_globs = re.findall(CYPRESS_EXCLUDE_SPEC_REGEX, cfgtext)
                if not include_globs:
                    # try default
                    include_globs = ["cypress/{e2e,component}/**/*.cy.{js,jsx,ts,tsx}",
                                     "cypress/{e2e,component}/*.cy.{js,jsx,ts,tsx}"
                                     ]

    specs = glob.glob(include_globs, root_dir=folder, flags=glob.BRACE, exclude=exclude_globs)
    if prefix:
        specs = [os.path.join(prefix, s) for s in specs]
    return specs


def build():
    """
    Build the distribution
    """
    testrun = app.get_testrun()
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

    logger.info(f'Using node {get_node_version()}')

    # create node environment
    create_node_environment(testrun)

    # build the app if required
    if testrun.project.build_cmd:
        build_app(testrun)

    # inform the main server so it can tell the agent to
    # start the runner job
    if testrun.project.test_framework == TestFramework.cypress:
        specs = get_cypress_specs(settings.src_dir, testrun.project.spec_filter)
    else:
        specs = get_playwright_specs(settings.src_dir, testrun.project.spec_filter)

    logger.debug(f'Parse specs: {specs}')
    app.post('build-completed', content=AgentBuildCompleted(specs=specs).json())


def prepare_cache():
    """
    Move the cachable stuff into root and delete the rest
    """

    if os.path.exists(f'{settings.src_dir}/node_modules') and not app.is_yarn_modern:
        runcmd(f'mv {settings.src_dir}/node_modules {settings.BUILD_DIR}')

    runcmd(f'rm -fr {settings.src_dir}')
    logger.info("Send cache_prepared event")

    app.post('cache-prepared')


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

