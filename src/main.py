import argparse
import asyncio
import datetime
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from time import time, sleep

import httpx
from httpx import HTTPError

from common.enums import TestResultStatus
from common.schemas import TestRunDetail, TestResult, TestResultError, CodeFrame, SpecResult

HUB_POLL_PERIOD = int(os.environ.get('HUB_POLL_PERIOD', 10))
RESULTS_FOLDER = os.environ.get('RESULTS_FOLDER', '/tmp/cykube/results')
ROOT_DIR = os.path.join(os.path.dirname(__file__), '..')
REPORTER_FILE = os.path.abspath(os.path.join(ROOT_DIR, 'json-reporter.js'))

BUILD_DIR='/tmp/cykube/build'

TOKEN = os.environ.get('API_TOKEN')
CYKUBE_API_URL = os.environ.get('CYKUBE_MAIN_URL', 'https://app.cykube.net/api')
CACHE_URL = os.environ.get('CACHE_URL', 'http://127.0.0.1:5001')
DIST_BUILD_TIMEOUT = os.environ.get('DIST_BUILD_TIMEOUT', 10*60)
CYPRESS_RUN_TIMEOUT = os.environ.get('CYPRESS_RUN_TIMEOUT', 10*60)

cykube_headers = {'Authorization': f'Bearer {TOKEN}'}


class BuildFailed(Exception):
    pass


def get_screenshots_folder():
    return os.path.join(RESULTS_FOLDER, 'screenshots')


def get_videos_folder():
    return os.path.join(RESULTS_FOLDER, 'videos')


def init_build_dirs():
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    os.makedirs(BUILD_DIR)
    os.makedirs(get_videos_folder(), exist_ok=True)
    os.makedirs(get_screenshots_folder(), exist_ok=True)


def get_cykube_client():
    client = httpx.AsyncClient()
    client.headers = cykube_headers
    return client


async def fetch_dist(id: int, sha: str) -> TestRunDetail:
    """
    Fetch the distribution from the cache server
    :param sha: commit SHA
    :param id: test run ID
    :return:
    """
    init_build_dirs()
    endtime = time() + DIST_BUILD_TIMEOUT
    logging.info("Waiting for build")
    while time() < endtime:
        async with get_cykube_client() as client:
            r = await client.get(f'{CYKUBE_API_URL}/testrun/{id}')
            if r.status_code != 200:
                raise BuildFailed(f"Failed to contact cykube: {r.status_code}")

            testrun = TestRunDetail(**r.json())
            status = testrun.status
            if status == 'running':
                # fetch the dist
                async with client.stream('GET', f'{CACHE_URL}/{sha}.tar.lz4') as r:
                    if r.status_code != 200:
                        raise BuildFailed("Distribution missing")
                    with tempfile.NamedTemporaryFile(suffix='.tar.lz4', mode='wb') as outfile:
                        async for chunk in r.aiter_bytes():
                            outfile.write(chunk)

                        # untar
                        subprocess.check_call(['/bin/tar', 'xf', outfile.name, '-I', 'lz4'], cwd=BUILD_DIR)
                return testrun
            elif status != 'building':
                raise BuildFailed("Build failed or cancelled: quit")

        # otherwise sleep
        sleep(HUB_POLL_PERIOD)

    raise BuildFailed("Reached timeout - quitting")


def get_env():
    env = os.environ.copy()
    env['PATH'] = f'{BUILD_DIR}/node_modules/.bin:{env["PATH"]}'
    return env


async def start_server(testrun: TestRunDetail) -> subprocess.Popen:
    """
    Start the server
    :return:
    """
    proc = subprocess.Popen(testrun.project.server_cmd, shell=True, cwd=BUILD_DIR, env=get_env())
    if not proc.pid:
        raise BuildFailed("Cannot start server")

    # wait until it's ready
    endtime = time() + 60
    logging.info("Waiting for server to be ready...")
    # wait 10 secs - trying to fetch from ng serve too soon can crash it
    sleep(10)
    while True:
        with httpx.AsyncClient() as client:
            r = await client.get(f'http://localhost:{testrun.project.server_port}')
            if r.status_code != 200:
                if time() > endtime:
                    raise BuildFailed('Failed to start server')
                sleep(5)
            else:
                return proc


def parse_results(started_at: datetime.datetime, spec: str) -> SpecResult:
    tests = []
    with open(os.path.join(RESULTS_FOLDER, 'out.json')) as f:
        rawjson = json.loads(f.read())
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

            filename = os.path.split(spec)[-1]
            sshots_folder = os.path.join(get_screenshots_folder(), filename)

            if err:
                # check for screenshots
                suffix = '' if not result.retry else f' (attempt {result.retry + 1})'
                failure_sshot = os.path.join(sshots_folder, f'{result.context} -- {result.title} (failed){suffix}.png')
                if not os.path.exists(failure_sshot):
                    failure_sshot = None
                else:
                    failure_sshot = failure_sshot[len(get_screenshots_folder())+1:]

                frame = err['codeFrame']
                result.error = TestResultError(title=err['name'],
                                               type=err['type'],
                                               message=err['message'],
                                               stack=err['stack'],
                                               screenshot=failure_sshot,
                                               code_frame=CodeFrame(line=frame['line'],
                                                                    column=frame['column'],
                                                                    language=frame['language'],
                                                                    frame=frame['frame']))

                if os.path.exists(get_videos_folder()):
                    video_files = list(os.listdir(get_videos_folder()))
                    if video_files:
                        # just pick the first one (should be only 1 surely?)
                        result.error.video = video_files[0]
            tests.append(result)

    # add skipped
    for skipped in rawjson.get('pending', []):
        tests.append(TestResult(status=TestResultStatus.skipped,
                                context=skipped['context'],
                                title=skipped['title']))

    return SpecResult(file=spec, tests=tests)


def run_cypress(file: str):
    results_file = f'{RESULTS_FOLDER}/out.json'
    result = subprocess.run(['cypress', 'run', '-s', file, '-q',
                             f'--reporter={REPORTER_FILE}',
                             '-o', f'output={results_file}',
                             '-c', f'screenshotsFolder={get_screenshots_folder()},screenshotOnRunFailure=true,'
                                   f'video=true,videosFolder={get_videos_folder()}'],
                            timeout=CYPRESS_RUN_TIMEOUT, capture_output=True, env=get_env(), cwd=BUILD_DIR)
    if result.returncode and result.stderr and not os.path.exists(results_file):
        logging.info('Cypress run failed: ' + result.stderr.decode())


async def upload_results(spec_id, result: SpecResult, client: httpx.AsyncClient):

    upload_url = f'{CYKUBE_API_URL}/hub/testrun/spec/{spec_id}/upload'

    for test in result.tests:
        if test.error:
            sshot = test.error.screenshot
            if sshot:
                fullpath = os.path.join(get_screenshots_folder(),
                                        os.path.split(result.file)[-1],
                                        sshot)
                r = await client.post(upload_url, files={'file': (sshot, open(fullpath, 'rb'), 'image/png')})
                if r.status_code != 200:
                    raise BuildFailed(f'Failed to upload screenshot to cykube: {r.status_code}')

            video = test.error.video
            if video:
                fullpath = os.path.join(get_videos_folder(), video)
                r = await client.post(upload_url, files={'file': (video, open(fullpath, 'rb'), 'video/mp4')})
                if r.status_code != 200:
                    raise BuildFailed(f'Failed to upload video to cykube: {r.status_code}')

    # finally upload result
    try:
        r = await client.post(f'{CYKUBE_API_URL}/hub/testrun/spec/{spec_id}/completed',
                              data=result.json().encode('utf8'))
        if not r.status_code == 200:
            raise BuildFailed(f'Test result post failed: {r.status_code}')
    except HTTPError:
        raise BuildFailed(f'Failed to contact Cykube server')


async def run_tests(testrun: TestRunDetail):

    while True:
        async with httpx.AsyncClient() as client:
            client.headers = cykube_headers
            r = await client.get(f'{CYKUBE_API_URL}/hub/testrun/{testrun.id}/next')
            if r.status_code == 204:
                # we're done
                break
            elif r.status_code == 200:
                # run the test
                spec = r.json()
                try:
                    started_at = datetime.datetime.now()
                    run_cypress(spec['file'])
                    result = parse_results(started_at, spec['file'])
                    await upload_results(spec['id'], result, client)
                    # cleanup
                    shutil.rmtree(RESULTS_FOLDER, ignore_errors=True)

                except subprocess.CalledProcessError as ex:
                    raise BuildFailed(f'Cypress run failed with return code {ex.returncode}')
                except subprocess.TimeoutExpired:
                    raise BuildFailed("Exceeded run timeout")
            else:
                raise BuildFailed(f"Received unexpected status code from hub: {r.status_code}")


async def run(testrun_id: int, sha: str):
    # fetch the distribution
    testrun = await fetch_dist(testrun_id, sha)
    # start the server
    proc = await start_server(testrun)

    try:
        # now fetch specs until we're done or the build is cancelled
        await run_tests(testrun)
    except Exception as ex:
        # TODO inform the server
        logging.error(ex)
        if proc:
            proc.kill()
            proc = None
    finally:
        # kill the server
        if proc:
            proc.kill()


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('id', help='Test run ID')
    parser.add_argument('sha', help='Commit SHA')

    args = parser.parse_args()
    # run in asyncio
    asyncio.run(run(args.id, args.sha))


if __name__ == '__main__':
    try:
        main()
        # test_upload()
        sys.exit(0)
    except Exception as ex:
        # bail out with an error - if we hit an OOM or similar we'll want to rerun the parent Job
        print(ex)
        sys.exit(1)
