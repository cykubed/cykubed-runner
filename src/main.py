import argparse
import asyncio
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from time import time, sleep

import httpx
from httpx import HTTPError
from loguru import logger

from common.enums import TestResultStatus
from common.schemas import TestRunDetail, TestResult, TestResultError, CodeFrame, SpecResult

HUB_POLL_PERIOD = int(os.environ.get('HUB_POLL_PERIOD', 10))
RESULTS_FOLDER = os.environ.get('RESULTS_FOLDER', '/tmp/cykube/results')
ROOT_DIR = os.path.join(os.path.dirname(__file__), '..')
REPORTER_FILE = os.path.abspath(os.path.join(ROOT_DIR, 'json-reporter.js'))

BUILD_DIR = '/tmp/cykube/build'

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
    return httpx.AsyncClient(headers=cykube_headers)


async def fetch_dist(id: int) -> TestRunDetail:
    """
    Fetch the distribution from the cache server
    :param sha: commit SHA
    :param id: test run ID
    :return:
    """
    init_build_dirs()
    endtime = time() + DIST_BUILD_TIMEOUT
    logger.info("Waiting for build")
    while time() < endtime:
        async with get_cykube_client() as client:
            r = await client.get(f'{CYKUBE_API_URL}/testrun/{id}')
            if r.status_code != 200:
                raise BuildFailed(f"Failed to contact cykube: {r.status_code}")

            testrun = TestRunDetail(**r.json())
            status = testrun.status
            if status == 'running':
                # fetch the dist
                async with client.stream('GET', f'{CACHE_URL}/{testrun.sha}.tar.lz4') as r:
                    if r.status_code != 200:
                        raise BuildFailed("Distribution missing")
                    logger.info('Fetch distribution')
                    with tempfile.NamedTemporaryFile(suffix='.tar.lz4', mode='wb') as outfile:
                        async for chunk in r.aiter_bytes():
                            outfile.write(chunk)

                        outfile.flush()
                        if not os.path.getsize(outfile.name):
                            raise BuildFailed("Zero-length dist file")
                        # untar
                        subprocess.check_call(['/bin/tar', 'xf', outfile.name, '-I', 'lz4'], cwd=BUILD_DIR)
                        logger.info('Unpacked distribution')
                return testrun
            elif status in ['failed', 'cancelled']:
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
    logger.info("Waiting for server to be ready...")
    # wait 10 secs - trying to fetch from ng serve too soon can crash it
    await asyncio.sleep(5)
    while True:
        async with httpx.AsyncClient() as client:
            r = await client.get(f'http://localhost:{testrun.project.server_port}')
            if r.status_code != 200:
                if time() > endtime:
                    raise BuildFailed('Failed to start server')
                await asyncio.sleep(5)
            else:
                logger.info('Server is ready')
                return proc


def parse_results(started_at: datetime.datetime, spec: str) -> SpecResult:
    tests = []
    failures = 0
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

            if err:
                failures += 1
                # check for screenshots
                sshot_fnames = []
                for root, dirs, files in os.walk(get_screenshots_folder()):
                    sshot_fnames += [os.path.join(root, f) for f in files]

                suffix = '' if not result.retry else f' (attempt {result.retry + 1})'
                expected = f'{result.context} -- {result.title} (failed){suffix}.png'

                failure_sshot = None
                for fname in sshot_fnames:
                    if os.path.split(fname)[-1] == expected:
                        failure_sshot = fname
                        break

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

            tests.append(result)

    # add skipped
    for skipped in rawjson.get('pending', []):
        tests.append(TestResult(status=TestResultStatus.skipped,
                                context=skipped['context'],
                                title=skipped['title']))

    result = SpecResult(file=spec, tests=tests)
    # we should have a single video - but only add it if we have failures
    if failures:
        video_fnames = []
        for root, dirs, files in os.walk(get_videos_folder()):
            video_fnames += [os.path.join(root, f) for f in files]

        if video_fnames:
            result.video = video_fnames[0]
    return result


def run_cypress(file: str):
    logger.info(f'Run Cypress for {file}')
    results_file = f'{RESULTS_FOLDER}/out.json'
    result = subprocess.run(['cypress', 'run', '-s', file, '-q',
                             f'--reporter={REPORTER_FILE}',
                             '-o', f'output={results_file}',
                             '-c', f'screenshotsFolder={get_screenshots_folder()},screenshotOnRunFailure=true,'
                                   f'video=true,videosFolder={get_videos_folder()}'],
                            timeout=CYPRESS_RUN_TIMEOUT, capture_output=True, env=get_env(), cwd=BUILD_DIR)
    if result.returncode and result.stderr and not os.path.exists(results_file):
        logger.error('Cypress run failed: ' + result.stderr.decode())


async def upload_results(spec_id, result: SpecResult):

    upload_url = f'{CYKUBE_API_URL}/agent/testrun/upload'

    async with get_cykube_client() as client:
        for test in result.tests:
            if test.error:
                sshot = test.error.screenshot
                if sshot:
                    # this will be the full path - we'll upload the file but just use the filename
                    filename = os.path.split(sshot)[-1]
                    logger.info(f'Upload screenshot {filename}')
                    r = await client.post(upload_url, files={'file': (sshot, open(sshot, 'rb'), 'image/png')},
                                          headers={'filename': filename})
                    if r.status_code != 200:
                        # TODO retry?
                        raise BuildFailed(f'Failed to upload screenshot to cykube: {r.status_code}')

                    test.error.screenshot = r.text

        if result.video:
            filename = os.path.split(result.video)[-1]
            logger.info(f'Upload video {filename}')
            r = await client.post(upload_url, files={'file': (result.video, open(result.video, 'rb'), 'video/mp4')},
                                  headers={'filename': filename})
            if r.status_code != 200:
                raise BuildFailed(f'Failed to upload video to cykube: {r.status_code}')
            result.video = r.text

        # finally upload result
        try:
            logger.info(f'Upload JSON results')
            r = await client.post(f'{CYKUBE_API_URL}/agent/testrun/spec/{spec_id}/completed',
                                  data=result.json().encode('utf8'))
            if not r.status_code == 200:
                raise BuildFailed(f'Test result post failed: {r.status_code}')
        except HTTPError:
            raise BuildFailed(f'Failed to contact Cykube server')


async def run_tests(testrun: TestRunDetail):

    while True:
        async with get_cykube_client() as client:
            r = await client.get(f'{CYKUBE_API_URL}/agent/testrun/{testrun.id}/next')
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
                    await upload_results(spec['id'], result)
                    # cleanup
                    shutil.rmtree(RESULTS_FOLDER, ignore_errors=True)

                except subprocess.CalledProcessError as ex:
                    raise BuildFailed(f'Cypress run failed with return code {ex.returncode}')
                except subprocess.TimeoutExpired:
                    raise BuildFailed("Exceeded run timeout")
            else:
                raise BuildFailed(f"Received unexpected status code from hub: {r.status_code}")


async def run(testrun_id: int):
    # fetch the distribution
    testrun = await fetch_dist(testrun_id)
    # start the server
    proc = await start_server(testrun)

    try:
        # now fetch specs until we're done or the build is cancelled
        await run_tests(testrun)
    except BuildFailed as ex:
        # TODO inform the server
        logger.exception(ex)
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
    parser.add_argument('--loglevel', default='debug', help='Log level')

    args = parser.parse_args()

    # run in asyncio
    asyncio.run(run(args.id))


if __name__ == '__main__':
    # asyncio.run(dummy_upload())
    try:
        main()
        sys.exit(0)
    except Exception as ex:
        # bail out with an error - if we hit an OOM or similar we'll want to rerun the parent Job
        print(ex)
        sys.exit(1)
