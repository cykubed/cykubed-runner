import asyncio
import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
from time import time, sleep

from httpx import AsyncClient

from common.enums import TestResultStatus, TestRunStatus
from common.exceptions import BuildFailedException
from common.fsclient import AsyncFSClient
from common.redisutils import sync_redis, async_redis, get_testrun
from common.schemas import TestResult, TestResultError, CodeFrame, SpecResult, NewTestRun, AgentRunnerStopped, \
    AgentSpecCompleted, AgentSpecStarted
from common.settings import settings
from common.utils import utcnow, get_hostname
from logs import logger
from server import start_server
from utils import set_status


def get_screenshots_folder():
    return os.path.join(settings.RESULTS_FOLDER, 'screenshots')


def get_videos_folder():
    return os.path.join(settings.RESULTS_FOLDER, 'videos')


def init_build_dirs():

    if os.path.exists(settings.BUILD_DIR):
        # probably running as developer
        shutil.rmtree(settings.BUILD_DIR, ignore_errors=True)
        os.makedirs(settings.BUILD_DIR, exist_ok=True)

    os.makedirs(get_videos_folder(), exist_ok=True)
    os.makedirs(get_screenshots_folder(), exist_ok=True)


def get_env():
    env = os.environ.copy()
    env['PATH'] = f'{settings.BUILD_DIR}/node_modules/.bin:{env["PATH"]}'
    env['CYPRESS_CACHE_FOLDER'] = 'cypress_cache'
    env['CYPRESS_RETRIES'] = '3'
    return env


def spec_terminated(trid: int, spec: str):
    """
    Return the spec to the pool
    """
    sync_redis().sadd(f'testrun:{trid}:specs', spec)


def parse_results(started_at: datetime.datetime) -> SpecResult:
    tests = []
    failures = 0
    with open(os.path.join(settings.RESULTS_FOLDER, 'out.json')) as f:
        rawjson = json.loads(f.read())

        sshot_fnames = []
        for root, dirs, files in os.walk(get_screenshots_folder()):
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
                try:
                    result.error = TestResultError(title=err['name'],
                                                   type=err.get('type'),
                                                   message=err['message'],
                                                   stack=err['stack'],
                                                   code_frame=CodeFrame(line=frame['line'],
                                                                        file=frame['relativeFile'],
                                                                        column=frame['column'],
                                                                        language=frame['language'],
                                                                        frame=frame['frame']))
                except:
                    raise BuildFailedException("Failed to parse test result")

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
        for root, dirs, files in os.walk(get_videos_folder()):
            video_fnames += [os.path.join(root, f) for f in files]

        if video_fnames:
            result.video = video_fnames[0]
    return result


def run_cypress(file: str, port: int):
    logger.debug(f'Run Cypress for {file}')
    results_file = f'{settings.RESULTS_FOLDER}/out.json'
    base_url = f'http://localhost:{port}'
    json_reporter = os.path.abspath(os.path.join(os.path.dirname(__file__), 'json-reporter.js'))
    result = subprocess.run(['cypress', 'run', '-s', file, '-q',
                             f'--reporter={json_reporter}',
                             '-o', f'output={results_file}',
                             '-c', f'screenshotsFolder={get_screenshots_folder()},screenshotOnRunFailure=true,'
                                   f'baseUrl={base_url},video=false,videosFolder={get_videos_folder()}'],
                            timeout=settings.CYPRESS_RUN_TIMEOUT, capture_output=True, env=get_env(), cwd=settings.BUILD_DIR)

    logger.debug(result.stdout.decode('utf8'))
    if result.returncode and result.stderr and not os.path.exists(results_file):
        logger.error('Cypress run failed: ' + result.stderr.decode())


async def upload(client, upload_url, sshot_file, mime_type, test_result):
    resp = await client.post(upload_url, files={'file': (sshot_file, open(sshot_file, 'rb'), mime_type)})
    if resp.status_code != 200:
        raise BuildFailedException(f'Failed to upload screenshot to cykube: {resp.status_code}')
    if mime_type.endswith('png'):
        test_result.failure_screenshots[test_result.failure_screenshots.index(sshot_file)] = resp.text
    else:
        test_result.video = resp.text


async def upload_results(spec: str, result: SpecResult, httpclient: AsyncClient):

    for test in result.tests:
        if test.failure_screenshots:
            for i, sshot in enumerate(test.failure_screenshots):
                resp = await httpclient.post('/artifact/upload',
                                         files={'file': (sshot, open(sshot, 'rb'), 'image/png')})
                if resp.status_code != 200:
                    logger.error(f'Failed to upload screenshot to cykube: {resp.status_code}')
                else:
                    test.failure_screenshots[i] = resp.text

    if result.video:
        resp = await httpclient.post('/artifact/upload',
                                 files={'file': (result.video, open(result.video, 'rb'), 'image/png')})
        if resp.status_code != 200:
            logger.error(f'Failed to upload video to cykube: {resp.status_code}')
        else:
            result.video = resp.text

    r = await httpclient.post('/spec-completed',
                              content=AgentSpecCompleted(
                                  result=result,
                                  file=spec,
                                  finished=utcnow()).json())
    if r.status_code != 200:
        raise BuildFailedException(f'Failed to set spec completed: {r.status_code}: {r.text}')


def default_sigterm_runner(signum, frame):
    """
    Default behaviour is just to log and quit with error code
    """
    logger.warning(f"SIGTERM/SIGINT caught: bailing out")
    sys.exit(1)


async def run_tests(testrun: NewTestRun, port: int, httpclient: AsyncClient):

    while True:

        hostname = get_hostname()

        spec = await async_redis().spop(f'testrun:{testrun.id}:specs')
        if not spec:
            # we're done
            logger.debug("No more tests - exiting")
            break

        r = await httpclient.post('/spec-started', content=AgentSpecStarted(file=spec,
                                                                         started=utcnow(),
                                                                         pod_name=hostname).json())
        if r.status_code != 200:
            raise BuildFailedException(f'Failed to update main server that spec has starter: {r.status_code}: {r.text}')

        def handle_sigterm_runner(signum, frame):
            """
            We can tell the agent that they should reassign the spec
            """
            spec_terminated(testrun.id, spec)
            logger.warning(f"SIGTERM/SIGINT caught: relinquish spec {spec}")
            sys.exit(0)

        signal.signal(signal.SIGTERM, handle_sigterm_runner)
        signal.signal(signal.SIGINT, handle_sigterm_runner)
        try:
            run_cypress(spec, port)
            result = parse_results(utcnow())
            await upload_results(spec, result, httpclient)

        except subprocess.CalledProcessError as ex:
            raise BuildFailedException(f'Cypress run failed with return code {ex.returncode}')
        except subprocess.TimeoutExpired:
            raise BuildFailedException("Exceeded run timeout")


async def runner_stopped(httpclient: AsyncClient, duration: int, terminated=False):
    r = await httpclient.post('/runner-stopped', content=AgentRunnerStopped(
        duration=duration,
        terminated=terminated).json())
    if r.status_code != 200:
        raise BuildFailedException(
            f"Failed to contact main server for closed runner: {r.status_code}: {r.text}")


async def run(testrun_id: int, httpclient: AsyncClient):
    logger.info(f'Starting Cypress run for testrun {testrun_id}')

    signal.signal(signal.SIGTERM, default_sigterm_runner)
    signal.signal(signal.SIGINT, default_sigterm_runner)

    fs = AsyncFSClient()
    start_time = time()
    try:
        init_build_dirs()
        await fs.connect()

        logger.init(testrun_id, source="runner")

        testrun = None

        while time() - start_time < settings.BUILD_TIMEOUT:
            testrun = await get_testrun(testrun_id)
            if testrun.status in [TestRunStatus.started, TestRunStatus.building]:
                logger.debug("Still building...")
                sleep(10)
            elif testrun.status == TestRunStatus.running:
                if not testrun.cache_key:
                    raise BuildFailedException("Missing cache key: quitting")
                logger.debug("Ready to run")
                break
            else:
                logger.info(f"Test run is {testrun.status}: quitting")
                return

        await asyncio.gather(fs.download_and_untar(f'{testrun.sha}.tar.lz4', settings.BUILD_DIR),
                             fs.download_and_untar(f'{testrun.cache_key}.tar.lz4', settings.BUILD_DIR))

        # start the server
        server = start_server()

        try:
            # now fetch specs until we're done or the build is cancelled
            logger.debug(f"Server running on port {server.port}")
            await run_tests(testrun, server.port, httpclient)
            await runner_stopped(httpclient, time() - start_time, False)
        finally:
            # kill the server
            server.stop()
    except Exception:
        logger.exception("Cypress run failed")
        await set_status(httpclient, TestRunStatus.failed)
        await runner_stopped(httpclient, time() - start_time, True)
        sys.exit(1)
    finally:
        await fs.close()


