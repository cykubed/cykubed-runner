import os
import signal
import sys

from cykubedrunner.app import app
from cykubedrunner.common.enums import TestFramework
from cykubedrunner.common.exceptions import RunFailedException
from cykubedrunner.common.schemas import NewTestRun
from cykubedrunner.common.utils import get_hostname
from cykubedrunner.cypress import CypressSpecRunner
from cykubedrunner.playwright import PlaywrightSpecRunner
from cykubedrunner.server import start_server, ServerThread
from cykubedrunner.settings import settings
from cykubedrunner.utils import logger, log_build_failed_exception, default_sigterm_runner, upload_results


def run_tests(server: ServerThread, testrun: NewTestRun):

    def spec_terminated(specfile: str):
        """
        Return the spec to the pool
        """
        app.post('return-spec', json={'file': specfile})

    while not app.is_terminating:

        hostname = get_hostname()
        r = app.post('next-spec', json={'pod_name': hostname})
        if r.status_code == 204:
            # we're finished
            logger.debug('No more spec file - quitting')
            return

        spec = r.text

        def handle_sigterm_runner(signum, frame):
            """
            We can tell the agent that they should reassign the spec
            """
            # it's possible we've actually just finished this (pretty edge case, but it has happened)
            app.is_terminating = True
            if spec not in app.specs_completed:
                spec_terminated(spec)
            logger.warning(f"SIGTERM/SIGINT caught: relinquish spec {spec}")
            sys.exit(1)

        if settings.K8 and not settings.TEST:
            signal.signal(signal.SIGTERM, handle_sigterm_runner)
            signal.signal(signal.SIGINT, handle_sigterm_runner)

        try:
            spectests = None
            if testrun.project.test_framework == TestFramework.cypress:
                # Cypress needs to be run explicitly for each required browser
                browsers = testrun.project.browsers or ['electron']
                logger.debug(f'Browsers = {browsers}')
                for browser in browsers:
                    logger.debug(f'Running Cypress tests for file {spec} on browser {browser}')
                    browser_spectests = CypressSpecRunner(server, testrun, spec,
                                                          browser=browser).run()
                    if not spectests:
                        spectests = browser_spectests
                    else:
                        spectests.merge(browser_spectests)
            else:
                # Playwright handles browser support natively
                logger.debug(f'Running Playwright tests for file {spec}')
                spectests = PlaywrightSpecRunner(server, testrun, spec).run()

            if spectests:
                upload_results(spec, spectests)

        except RunFailedException as ex:
            log_build_failed_exception(ex)
            return
        except Exception as ex:
            # something went wrong - push the spec back onto the stack
            logger.exception(f'Runner failed unexpectedly: adding the spec back to the stack')
            # FIXME too broad? Probably, although in this case we probably do want to catch stuff
            # like OOM, etc
            spec_terminated(spec)
            raise ex


def run():
    testrun = app.get_testrun()
    if not testrun:
        logger.info(f"Missing test run: quitting")
        return

    logger.init(testrun.id, source="runner")
    logger.info(f'Starting runner for testrun {testrun.id}')

    if settings.K8 and not settings.TEST:
        signal.signal(signal.SIGTERM, default_sigterm_runner)
        signal.signal(signal.SIGINT, default_sigterm_runner)

    srcnode = os.path.join(settings.src_dir, 'node_modules')
    if not os.path.exists(srcnode):
        raise RunFailedException("Missing node_modules")

    # start the server
    server = start_server(testrun.project)
    logger.debug(f"Server running on port {server.port}")

    # now fetch specs until we're done or the build is cancelled
    run_tests(server, testrun)

    server.stop()
