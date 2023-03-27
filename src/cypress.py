import asyncio
import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
from time import time, sleep

import httpx

from common.db import get_testrun, next_spec, send_status_message, send_spec_completed_message, spec_terminated
from common.enums import TestResultStatus, TestRunStatus
from common.exceptions import BuildFailedException
from common.fsclient import AsyncFSClient
from common.schemas import TestResult, TestResultError, CodeFrame, SpecResult, NewTestRun
from common.settings import settings
from common.utils import utcnow
from logs import logger
from server import start_server


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
    return env


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
                                   f'baseUrl={base_url},video=true,videosFolder={get_videos_folder()}'],
                            timeout=settings.CYPRESS_RUN_TIMEOUT, capture_output=True, env=get_env(), cwd=settings.BUILD_DIR)

    logger.debug(result.stdout.decode('utf8'))
    if result.returncode and result.stderr and not os.path.exists(results_file):
        logger.error('Cypress run failed: ' + result.stderr.decode())


async def upload_results(testrun: NewTestRun, spec: str, result: SpecResult):

    # For now upload images and videos directly to the main service rather than via the websocket
    # This may change
    upload_url = f'{settings.MAIN_API_URL}/agent/testrun/upload/{testrun.project.id}'

    transport = httpx.AsyncHTTPTransport(retries=settings.MAX_HTTP_RETRIES)

    tasks = []
    # upload them in parallel
    async with httpx.AsyncClient(transport=transport,
                                 headers={'Authorization': f'Bearer {settings.API_TOKEN}'}) as client:

        async def upload(sshot_file, mime_type, test_result=None):
            resp = await client.post(upload_url, files={'file': (sshot_file, open(sshot_file, 'rb'), mime_type)})
            if resp.status_code != 200:
                raise BuildFailedException(f'Failed to upload screenshot to cykube: {resp.status_code}')
            if test_result:
                test_result.failure_screenshots[test.failure_screenshots.index(sshot_file)] = resp.text
            else:
                result.video = resp.text

        for test in result.tests:
            if test.failure_screenshots:
                for sshot in test.failure_screenshots:
                    # this will be the full path - we'll upload the file but just use the filename
                    tasks.append(asyncio.create_task(upload(sshot, 'image/png', test)))

        if result.video:
            tasks.append(asyncio.create_task(upload(result.video, 'video/mp4')))

        if tasks:
            await asyncio.gather(*tasks)

    # finally upload result to agent
    await send_spec_completed_message(testrun, spec, result)


async def run_tests(testrun: NewTestRun, port: int):

    while True:
        with open('/etc/hostname') as f:
            hostname = f.read().strip()

        spec = await next_spec(testrun.id, hostname)
        if not spec:
            # we're done
            logger.debug("No more tests - exiting")
            break

        def handle_sigterm_runner(signum, frame):
            """
            We can tell the agent that they should reassign the spec
            """
            spec_terminated(testrun.id, spec)
            logger.info(f"SIGTERM/SIGINT caught: relinquish spec {spec}")
            sys.exit(1)

        signal.signal(signal.SIGTERM, handle_sigterm_runner)
        signal.signal(signal.SIGINT, handle_sigterm_runner)
        try:
            run_cypress(spec, port)
            result = parse_results(utcnow())
            await upload_results(testrun, spec, result)

        except subprocess.CalledProcessError as ex:
            raise BuildFailedException(f'Cypress run failed with return code {ex.returncode}')
        except subprocess.TimeoutExpired:
            raise BuildFailedException("Exceeded run timeout")


async def run(testrun_id: int):
    fs = AsyncFSClient()
    try:
        init_build_dirs()
        await fs.connect()

        logger.init(testrun_id, source="runner")

        start_time = time()
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
            await run_tests(testrun, server.port)
        finally:
            # kill the server
            server.stop()

    except BuildFailedException:
        logger.exception("Cypress run failed")
        await send_status_message(testrun_id, 'failed')
        sys.exit(1)
    finally:
        await fs.close()


