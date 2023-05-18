import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from time import time

from httpx import Client
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_fixed, wait_random

from common.enums import TestResultStatus, TestRunStatus, AgentEventType
from common.exceptions import RunFailedException
from common.redisutils import sync_redis, get_specfile_log_key
from common.schemas import TestResult, TestResultError, CodeFrame, SpecResult, AgentSpecCompleted, \
    AgentSpecStarted, NewTestRun, AgentEvent
from common.utils import utcnow, get_hostname
from server import start_server, ServerThread
from settings import settings
from utils import set_status, get_testrun, logger, runcmd, send_agent_event


def spec_terminated(trid: int, spec: str):
    """
    Return the spec to the pool
    """
    sync_redis().sadd(f'testrun:{trid}:specs', spec)


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
                frame = err['codeFrame']

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
                                                   code_frame=CodeFrame(line=frame['line'],
                                                                        file=frame['relativeFile'],
                                                                        column=frame['column'],
                                                                        language=frame['language'],
                                                                        frame=frame['frame']))
                except:
                    raise RunFailedException("Failed to parse test result")

            tests.append(result)

    # add skipped
    for skipped in rawjson.get('pending', []):
        tests.append(TestResult(status=TestResultStatus.skipped,
                                context=skipped['context'],
                                title=skipped['title']))

    result = SpecResult(tests=tests)
    # we should have a single video - but only add it if we have failures
    if failures:
        video_fnames = []
        for root, dirs, files in os.walk(settings.get_videos_folder()):
            video_fnames += [os.path.join(root, f) for f in files]

        if video_fnames:
            result.video = video_fnames[0]
    return result


class RedisLogPipe(threading.Thread):
    def __init__(self, trid: int, file: str):
        threading.Thread.__init__(self)
        self.daemon = True
        self.trid = trid
        self.fdRead, self.fdWrite = os.pipe()
        self.pipeReader = os.fdopen(self.fdRead)
        self.start()
        self.redis = sync_redis()
        self.key = get_specfile_log_key(trid, file)
        self.redis.delete(self.key)
        self.redis.expire(self.key, 60)
        self.lines = 0

    def fileno(self):
        """Return the write file descriptor of the pipe
        """
        return self.fdWrite

    def run(self):
        """Run the thread, logging everything.
        """
        for line in iter(self.pipeReader.readline, ''):
            self.redis.rpush(self.key, line)
            logger.debug(f'Cypress: {line}')
            self.lines += 1

        self.pipeReader.close()

    def close(self):
        """Close the write end of the pipe.
        """
        os.close(self.fdWrite)


class CypressSpecRunner(object):
    def __init__(self, server: ServerThread, testrun: NewTestRun, httpclient: Client, file: str):
        self.server = server
        self.testrun = testrun
        self.file = file
        self.httpclient = httpclient
        self.results_dir = settings.get_results_dir()
        self.results_file = f'{self.results_dir}/out.json'
        if os.path.exists(self.results_dir):
            shutil.rmtree(self.results_dir)
        os.makedirs(self.results_dir)
        if self.testrun.project.cypress_debug_enabled:
            self.logpipe = RedisLogPipe(self.testrun.id, self.file)
            self.stdout = self.logpipe
        else:
            self.logpipe = None
            self.stdout = subprocess.DEVNULL
        self.started = None

    def get_args(self):
        base_url = f'http://localhost:{self.server.port}'
        json_reporter = os.path.abspath(os.path.join(os.path.dirname(__file__), 'json-reporter.js'))

        return ['cypress', 'run',
                '-q',
                '--browser', self.testrun.project.browser or 'electron',
                '-s', self.file,
                '--reporter', json_reporter,
                '-o', f'output={self.results_file}',
                '-c', f'screenshotsFolder={settings.get_screenshots_folder()},screenshotOnRunFailure=true,'
                      f'baseUrl={base_url},video=false,videosFolder={settings.get_videos_folder()}']

    def get_env(self):
        env = os.environ.copy()
        env.update(CYPRESS_CACHE_FOLDER=f'{settings.NODE_CACHE_DIR}/cypress_cache',
                   PATH=f'node_modules/.bin:{env["PATH"]}')

        if self.testrun.project.cypress_retries:
            env['CYPRESS_RETRIES'] = str(self.testrun.project.cypress_retries)
        if self.testrun.project.cypress_debug_enabled:
            env['DEBUG'] = 'cypress:*'
        return env

    def run(self):
        self.started = utcnow()
        logger.debug(f'Run Cypress for {self.file}')
        self.create_cypress_process()

        if not os.path.exists(self.results_file):
            raise RunFailedException(f'Missing results file')

        # parse and upload the results
        result = parse_results(self.started, self.file)

        upload_results(self.file, result, self.httpclient)
        completions_remaining = spec_completed(self.testrun.id)
        logger.debug(f'{completions_remaining} specs remaining')
        if not completions_remaining:
            # no more completions - we're done
            logger.info(f'Run completed')
            send_agent_event(AgentEvent(type=AgentEventType.run_completed,
                                        testrun_id=self.testrun.id))

    def create_cypress_process(self):
        args = self.get_args()
        fullcmd = ' '.join(args)
        logger.debug(f'Calling cypress with args: "{fullcmd}"')

        try:
            result = subprocess.run(args,
                                    timeout=self.testrun.project.spec_deadline or None,
                                    capture_output=True,
                                    text=True,
                                    env=self.get_env(),
                                    cwd=settings.dist_dir)
            logger.debug(f'Cypress stdout: \n{result.stdout}')
            logger.debug(f'Cypress stderr: \n{result.stderr}')
        except subprocess.TimeoutExpired as ex:
            logger.debug(f'Spec activity deadline exceeded for {self.file}')
            raise ex


@retry(retry=retry_if_not_exception_type(RunFailedException),
       stop=stop_after_attempt(settings.MAX_HTTP_RETRIES),
       wait=wait_fixed(2) + wait_random(0, 4))
def upload(client, sshot_file, mime_type='image/png') -> str:
    logger.info(f'Uploading file {sshot_file} to server')
    resp = client.post('/artifact/upload',
                        files={'file': (sshot_file, open(sshot_file, 'rb'), mime_type)})
    if resp.status_code != 200:
        raise RunFailedException(f'Failed to upload screenshot to cykube: {resp.status_code}')
    return resp.text


def upload_results(spec: str, result: SpecResult, httpclient: Client):

    for test in result.tests:
        if test.failure_screenshots:
            for i, sshot in enumerate(test.failure_screenshots):
                test.failure_screenshots[i] = upload(httpclient, sshot)

    if result.video:
        result.video = upload(result.video, 'video/mp4')

    r = httpclient.post('/spec-completed',
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


def run_tests(server: ServerThread, testrun: NewTestRun, httpclient: Client):

    while True:

        hostname = get_hostname()

        redis = sync_redis()
        spec = redis.spop(f'testrun:{testrun.id}:specs')
        if not spec:
            # we're done
            logger.debug("No more tests - exiting")
            return

        r = httpclient.post('/spec-started', content=AgentSpecStarted(file=spec,
                                                                      started=utcnow(),
                                                                      pod_name=hostname).json())
        if r.status_code != 200:
            raise RunFailedException(f'Failed to update main server that spec has started: {r.status_code}: {r.text}')

        def handle_sigterm_runner(signum, frame):
            """
            We can tell the agent that they should reassign the spec
            """
            spec_terminated(testrun.id, spec)
            logger.warning(f"SIGTERM/SIGINT caught: relinquish spec {spec}")
            sys.exit(1)

        if settings.K8:
            signal.signal(signal.SIGTERM, handle_sigterm_runner)
            signal.signal(signal.SIGINT, handle_sigterm_runner)

        # run cypress for this spec
        try:
            CypressSpecRunner(server, testrun, httpclient, spec).run()
        except Exception as ex:
            # something went wrong - push the spec back onto the stack
            logger.exception(f'Runner failed unexpectedly: add the spec back to the stack')
            redis.sadd(f'testrun:{testrun.id}:specs', spec)
            # sleep(3600)
            raise ex

        # sleep(3600)


def runner_stopped(trid: int, duration: int):
    sync_redis().incrby(f'testrun:{trid}:run_duration', duration)


def get_total_run_duration(trid: int) -> int:
    return sync_redis().get(f'testrun:{trid}:run_duration')


def spec_completed(trid: int) -> int:
    """
    Decrement the to-complete count and return the new value
    """
    return sync_redis().decr(f'testrun:{trid}:to-complete')


def run(testrun_id: int, httpclient: Client):
    logger.info(f'Starting Cypress run for testrun {testrun_id}')

    if settings.K8:
        signal.signal(signal.SIGTERM, default_sigterm_runner)
        signal.signal(signal.SIGINT, default_sigterm_runner)

    start_time = time()
    try:
        logger.init(testrun_id, source="runner")

        testrun = get_testrun(testrun_id)
        if not testrun:
            logger.info(f"Missing test run: quitting")
            return

        srcnode = os.path.join(settings.NODE_CACHE_DIR, 'node_modules')
        if not os.path.exists(srcnode):
            raise RunFailedException("Missing node_modules")

        srccypress = os.path.join(settings.NODE_CACHE_DIR, 'cypress_cache')
        if not os.path.exists(srccypress):
            raise RunFailedException("Missing cypress cache folder")

        # annoyingly Cypress won't run directly on a RO filesystem (even though it runs happily on a RO folder locally)
        # so symlink everything into the scratch folder
        runcmd(f"ln -s {settings.BUILD_DIR}/* {settings.dist_dir}")

        # start the server
        server = start_server()

        try:
            # now fetch specs until we're done or the build is cancelled
            logger.debug(f"Server running on port {server.port}")
            run_tests(server, testrun, httpclient)
        finally:
            # kill the server
            server.stop()
    except RunFailedException:
        logger.exception("Cypress run failed")
        set_status(httpclient, TestRunStatus.failed)
        # sleep(3600)
        sys.exit(1)
    finally:
        runner_stopped(testrun_id, int(time() - start_time))



