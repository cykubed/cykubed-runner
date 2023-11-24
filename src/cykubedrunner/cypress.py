import datetime
import json
import os
import shutil
import signal
import subprocess
import sys

from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_fixed, wait_random

from cykubedrunner.app import app
from cykubedrunner.common.enums import TestResultStatus
from cykubedrunner.common.exceptions import RunFailedException
from cykubedrunner.common.schemas import TestResult, TestResultError, CodeFrame, SpecResult, AgentSpecCompleted, \
    NewTestRun
from cykubedrunner.common.utils import utcnow, get_hostname
from cykubedrunner.server import start_server, ServerThread
from cykubedrunner.settings import settings
from cykubedrunner.utils import get_testrun, logger, log_build_failed_exception


def parse_results(started_at: datetime.datetime, spec_file: str) -> SpecResult:
    tests = []
    failures = 0
    with open(os.path.join(settings.get_results_dir(), 'out.json')) as f:
        rawjson = json.loads(f.read())

        sshot_fnames = []
        for root, dirs, files in os.walk(settings.get_screenshots_folder()):
            sshot_fnames += [os.path.join(root, f) for f in files]

        for test in rawjson['tests']:
            err = test.get('err')

            if 'duration' not in test:
                continue

            result = TestResult(title=test['title'],
                                context=test['context'],
                                status=TestResultStatus.failed if err else TestResultStatus.passed,
                                retry=test['currentRetry'],
                                duration=test['duration'],
                                started_at=started_at.isoformat(),
                                finished_at=datetime.datetime.now().isoformat())

            # check for screenshots
            prefix = f'{result.context} -- {result.title} (failed)'
            sshots = []
            for fname in sshot_fnames:
                if os.path.split(fname)[-1].startswith(prefix):
                    sshots.append(fname)
            if sshots:
                result.failure_screenshots = sshots

            if err:
                failures += 1
                frame = err.get('codeFrame')
                if not frame:
                    fullerror = json.dumps(err)
                    logger.warning(f"No code frame: full error: {fullerror}")
                else:
                    codeframe = CodeFrame(line=frame['line'],
                                          file=frame['relativeFile'],
                                          column=frame['column'],
                                          language=frame['language'],
                                          frame=frame['frame'])
                # get line number of test
                testline = 0
                for parsed in err['parsedStack']:
                    if 'relativeFile' in parsed and parsed['relativeFile'].endswith(spec_file):
                        testline = parsed['line']
                        break

                try:
                    result.error = TestResultError(title=err['name'],
                                                   type=err.get('type'),
                                                   test_line=testline,
                                                   message=err['message'],
                                                   stack=err['stack'],
                                                   code_frame=codeframe)
                except:
                    raise RunFailedException("Failed to parse test result")

            tests.append(result)

    result = SpecResult(tests=tests)
    # we should have a single video - but only add it if we have failures
    if failures:
        video_fnames = []
        for root, dirs, files in os.walk(settings.get_videos_folder()):
            video_fnames += [os.path.join(root, f) for f in files]

        if video_fnames:
            result.video = video_fnames[0]
    return result


class CypressSpecRunner(object):

    def __init__(self, server: ServerThread, testrun: NewTestRun, file: str):
        self.server = server
        self.testrun = testrun
        self.file = file
        self.results_dir = settings.get_results_dir()
        self.results_file = f'{self.results_dir}/out.json'
        if os.path.exists(self.results_dir):
            shutil.rmtree(self.results_dir)
        os.makedirs(self.results_dir)
        self.started = None

    def get_args(self):
        base_url = f'http://localhost:{self.server.port}'
        json_reporter = os.path.abspath(os.path.join(os.path.dirname(__file__), 'json-reporter.js'))

        return ['cypress', 'run',
                '-q',
                '--browser', self.testrun.project.docker_image.browser or 'electron',
                '-s', self.file,
                '--reporter', json_reporter,
                '-o', f'output={self.results_file}',
                '-c', f'screenshotsFolder={settings.get_screenshots_folder()},screenshotOnRunFailure=true,'
                      f'baseUrl={base_url},video=false,videosFolder={settings.get_videos_folder()}']

    def get_env(self):
        env = os.environ.copy()
        env.update(CYPRESS_CACHE_FOLDER=f'{settings.BUILD_DIR}/cypress_cache',
                   PATH=f'node_modules/.bin:{env["PATH"]}')

        if self.testrun.project.cypress_retries:
            env['CYPRESS_RETRIES'] = str(self.testrun.project.cypress_retries)
        return env

    def run(self):
        self.started = utcnow()
        logger.debug(f'Run Cypress for {self.file}')
        try:
            proc = self.create_cypress_process()
            if not os.path.exists(self.results_file):
                if proc.returncode == 1:
                    # there was a problem with the run - log output
                    logger.error(f"Cypress run failed to produce any results:\n {proc.stdout}\n{proc.stderr}")
                raise RunFailedException(f'Missing results file')

            # parse and upload the results
            result = parse_results(self.started, self.file)

            upload_results(self.file, result)
        except subprocess.TimeoutExpired:
            logger.info(f'Exceeded deadline for spec {self.file}')

            r = self.httpclient.post('/spec-completed',
                                content=AgentSpecCompleted(
                                    result=SpecResult(timeout=True, tests=[]),
                                    file=self.file,
                                    finished=utcnow()).json())
            if r.status_code != 200:
                raise RunFailedException(f'Failed to set spec completed: {r.status_code}: {r.text}')

    def create_cypress_process(self) -> subprocess.CompletedProcess:
        args = self.get_args()
        fullcmd = ' '.join(args)
        logger.debug(f'Calling cypress with args: "{fullcmd}"')

        result = subprocess.run(args,
                                timeout=self.testrun.project.spec_deadline or None,
                                capture_output=True,
                                text=True,
                                env=self.get_env(),
                                cwd=settings.src_dir)
        logger.debug(f'Cypress stdout: \n{result.stdout}')
        logger.debug(f'Cypress stderr: \n{result.stderr}')
        return result


@retry(retry=retry_if_not_exception_type(RunFailedException),
       stop=stop_after_attempt(settings.MAX_HTTP_RETRIES if not settings.TEST else 1),
       wait=wait_fixed(2) + wait_random(0, 4))
def upload_files(files) -> list[str]:
    resp = app.http_client.post('/upload-artifacts', files=files)
    if resp.status_code != 200:
        raise RunFailedException(f'Failed to upload screenshot to cykube: {resp.status_code}')
    return resp.json()['urls']


def upload_results(spec: str, result: SpecResult):
    files = []

    for test in result.tests:
        if test.failure_screenshots:
            for sshot in test.failure_screenshots:
                files.append(('files', open(sshot, 'rb')))

    if result.video:
        files.append(('files', open(result.video, 'rb')))

    if files:
        urls = upload_files(files)
        for test in result.tests:
            if test.failure_screenshots:
                num = len(test.failure_screenshots)
                test.failure_screenshots = urls[:num]
                urls = urls[num:]
        if urls:
            result.video = urls[0]

    r = app.http_client.post('/spec-completed',
                        content=AgentSpecCompleted(
                            result=result,
                            file=spec,
                            finished=utcnow()).json())

    if r.status_code != 200:
        raise RunFailedException(f'Failed to set spec completed: {r.status_code}: {r.text}')


def default_sigterm_runner(signum, frame):
    """
    Default behaviour is just to log and quit with error code
    """
    logger.warning(f"SIGTERM/SIGINT caught: bailing out")
    sys.exit(1)


def run_tests(server: ServerThread, testrun: NewTestRun):

    def spec_terminated(specfile: str):
        """
        Return the spec to the pool
        """
        resp = app.http_client.post('/return-spec', json={'file': specfile})
        if resp.status_code != 200:
            logger.error(f'Failed to return spec to queue: {r.status_code}: {r.text}')

    while not app.is_terminating:

        hostname = get_hostname()
        r = app.http_client.post('/next-spec', json={'pod_name': hostname})
        if r.status_code == 204:
            # we're finished
            logger.debug('No more spec file - quitting')
            return
        if r.status_code != 200:
            raise RunFailedException(
                f'Failed to request next spec from server: {r.status_code}: {r.text} - bailing out')

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

        # run cypress for this spec
        try:
            CypressSpecRunner(server, testrun, spec).run()
        except RunFailedException as ex:
            log_build_failed_exception(testrun.id, ex)
            return
        except Exception as ex:
            # something went wrong - push the spec back onto the stack
            logger.exception(f'Runner failed unexpectedly: adding the spec back to the stack')
            # FIXME too broad? Probably, although in this case we probably do want to catch stuff
            # like OOM, etc
            spec_terminated(spec)
            raise ex


def run(testrun_id: int):
    logger.info(f'Starting Cypress run for testrun {testrun_id}')

    if settings.K8 and not settings.TEST:
        signal.signal(signal.SIGTERM, default_sigterm_runner)
        signal.signal(signal.SIGINT, default_sigterm_runner)

    logger.init(testrun_id, source="runner")

    testrun = get_testrun(testrun_id)
    if not testrun:
        logger.info(f"Missing test run: quitting")
        return

    srcnode = os.path.join(settings.src_dir, 'node_modules')
    if not os.path.exists(srcnode):
        raise RunFailedException("Missing node_modules")

    srccypress = os.path.join(settings.BUILD_DIR, 'cypress_cache')
    if not os.path.exists(srccypress):
        raise RunFailedException("Missing cypress cache folder")

    # start the server
    server = start_server(testrun.project)
    logger.debug(f"Server running on port {server.port}")

    # now fetch specs until we're done or the build is cancelled
    run_tests(server, testrun)

    server.stop()
