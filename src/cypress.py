import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
from time import time, sleep

from httpx import Client

from common.enums import TestResultStatus, TestRunStatus, AgentEventType
from common.exceptions import RunFailedException
from common.redisutils import sync_redis
from common.schemas import TestResult, TestResultError, CodeFrame, SpecResult, AgentSpecCompleted, \
    AgentSpecStarted, NewTestRun, AgentEvent
from common.utils import utcnow, get_hostname
from server import start_server
from settings import settings
from utils import set_status, get_testrun, send_agent_event, logger


def spec_terminated(trid: int, spec: str):
    """
    Return the spec to the pool
    """
    sync_redis().sadd(f'testrun:{trid}:specs', spec)


def parse_results(started_at: datetime.datetime) -> SpecResult:
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


def run_cypress(testrun: NewTestRun, file: str, port: int):
    logger.debug(f'Run Cypress for {file}')
    results_dir = settings.get_results_dir()
    if os.path.exists(results_dir):
        shutil.rmtree(results_dir)
    os.makedirs(results_dir)
    results_file = f'{results_dir}/out.json'
    base_url = f'http://localhost:{port}'
    json_reporter = os.path.abspath(os.path.join(os.path.dirname(__file__), 'json-reporter.js'))

    env = os.environ.copy()
    env['CYPRESS_CACHE_FOLDER'] = f'{settings.RW_BUILD_DIR}/cypress_cache'
    if testrun.project.cypress_retries:
        env['CYPRESS_RETRIES'] = str(testrun.project.cypress_retries)
        env['CYPRESS_RETRIES'] = str(testrun.project.cypress_retries)
    env['PATH'] = f'{settings.NODE_CACHE_DIR}/node_modules/.bin:{env["PATH"]}'

    dist_dir = os.path.join(settings.RW_BUILD_DIR, 'dist')
    result = subprocess.run(['cypress', 'run',
                             '-q',
                             '--browser', testrun.project.browser,
                             '-s', file,
                             '--reporter', json_reporter,
                             '-o', f'output={results_file}',
                             '-c', f'screenshotsFolder={settings.get_screenshots_folder()},screenshotOnRunFailure=true,'
                                   f'baseUrl={base_url},video=false,videosFolder={settings.get_videos_folder()}'],
                            timeout=settings.CYPRESS_RUN_TIMEOUT, capture_output=True,
                            env=env, cwd=dist_dir)

    logger.debug(result.stdout.decode('utf8'))
    if result.returncode and result.stderr and not os.path.exists(results_file):
        logger.error('Cypress run failed: ' + result.stderr.decode())

    # runcmd(f'cypress run -s {file} -q --reporter={json_reporter} -o output={results_file} -c screenshotsFolder={settings.get_screenshots_folder()},screenshotOnRunFailure=true,baseUrl={base_url},video=false,videosFolder={settings.get_videos_folder()}',
    #        timeout=settings.CYPRESS_RUN_TIMEOUT,
    #        env=env, cwd=dist_dir, log=True)


async def upload(client, upload_url, sshot_file, mime_type, test_result):
    resp = await client.post(upload_url, files={'file': (sshot_file, open(sshot_file, 'rb'), mime_type)})
    if resp.status_code != 200:
        raise RunFailedException(f'Failed to upload screenshot to cykube: {resp.status_code}')
    if mime_type.endswith('png'):
        test_result.failure_screenshots[test_result.failure_screenshots.index(sshot_file)] = resp.text
    else:
        test_result.video = resp.text


def upload_results(trid: int, spec: str, result: SpecResult, httpclient: Client):

    for test in result.tests:
        if test.failure_screenshots:
            for i, sshot in enumerate(test.failure_screenshots):
                resp = httpclient.post('/artifact/upload',
                                         files={'file': (sshot, open(sshot, 'rb'), 'image/png')})
                if resp.status_code != 200:
                    logger.error(f'Failed to upload screenshot to cykube: {resp.status_code}')
                else:
                    test.failure_screenshots[i] = resp.text

    if result.video:
        resp = httpclient.post('/artifact/upload',
                                 files={'file': (result.video, open(result.video, 'rb'), 'image/png')})
        if resp.status_code != 200:
            logger.error(f'Failed to upload video to cykube: {resp.status_code}')
        else:
            result.video = resp.text

    r = httpclient.post('/spec-completed',
                              content=AgentSpecCompleted(
                                  result=result,
                                  total_run_duration=get_total_run_duration(trid),
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


def run_tests(testrun: NewTestRun, port: int, httpclient: Client):

    while True:

        hostname = get_hostname()

        redis = sync_redis()
        spec = redis.spop(f'testrun:{testrun.id}:specs')
        if not spec:
            # we're done
            logger.debug("No more tests - exiting")
            # tell the agent
            send_agent_event(AgentEvent(type=AgentEventType.run_completed,
                                        testrun_id=testrun.id))
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
            sys.exit(0)

        signal.signal(signal.SIGTERM, handle_sigterm_runner)
        signal.signal(signal.SIGINT, handle_sigterm_runner)
        try:
            started = utcnow()
            run_cypress(testrun, spec, port)
            result = parse_results(started)
            upload_results(testrun.id, spec, result, httpclient)

        except subprocess.CalledProcessError as ex:
            raise RunFailedException(f'Cypress run failed with return code {ex.returncode}')
        except subprocess.TimeoutExpired:
            raise RunFailedException("Exceeded run timeout")


def runner_stopped(trid: int, duration: int):
    sync_redis().incrby(f'testrun:{trid}:run_duration', duration)


def get_total_run_duration(trid: int) -> int:
    return sync_redis().get(f'testrun:{trid}:run_duration')


def run(testrun_id: int, httpclient: Client):
    logger.info(f'Starting Cypress run for testrun {testrun_id}')

    signal.signal(signal.SIGTERM, default_sigterm_runner)
    signal.signal(signal.SIGINT, default_sigterm_runner)

    start_time = time()
    try:
        logger.init(testrun_id, source="runner")

        testrun = get_testrun(testrun_id)
        if not testrun:
            logger.info(f"Missing test run: quitting")
            return

        # need to copy the build dist to a RW folder
        shutil.copytree(settings.BUILD_DIR, settings.RW_BUILD_DIR, ignore_dangling_symlinks=True,
                        ignore=shutil.ignore_patterns('node_modules'))

        srcnode = os.path.join(settings.NODE_CACHE_DIR, 'node_modules')
        if not os.path.exists(srcnode):
            raise RunFailedException("Missing node_modules")
        os.symlink(srcnode, os.path.join(settings.RW_BUILD_DIR, 'dist', 'node_modules'))

        # ditto for the Cypress folder cache
        srccypress = os.path.join(settings.NODE_CACHE_DIR, 'cypress_cache')
        if not os.path.exists(srccypress):
            raise RunFailedException("Missing cypress cache folder")
        shutil.copytree(srccypress,
                        os.path.join(settings.RW_BUILD_DIR, 'cypress_cache'))

        # start the server
        server = start_server()

        try:
            # now fetch specs until we're done or the build is cancelled
            logger.debug(f"Server running on port {server.port}")
            run_tests(testrun, server.port, httpclient)
        finally:
            # kill the server
            server.stop()
    except RunFailedException:
        logger.exception("Cypress run failed")
        set_status(httpclient, TestRunStatus.failed)
        sleep(3600)
        sys.exit(1)
    finally:
        runner_stopped(testrun_id, int(time() - start_time))



