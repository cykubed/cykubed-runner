import argparse
import datetime
import json
import logging
import os
import shutil
import subprocess
import sys
from time import time, sleep

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from common.enums import TestResultStatus
from common.schemas import TestRun, TestResult, TestResultError, CodeFrame, SpecResult

HUB_POLL_PERIOD = int(os.environ.get('HUB_POLL_PERIOD', 10))
RESULTS_FOLDER = os.environ.get('RESULTS_FOLDER', 'cykube/results')
# SCREENSHOTS_FOLDER = os.path.join(RESULTS_FOLDER, 'screenshots')
# VIDEOS_FOLDER = os.path.join(RESULTS_FOLDER, 'videos')

TOKEN = os.environ.get('CYKUBE_HUB_TOKEN')
CYKUBE_MAIN_URL = os.environ.get('CYKUBE_MAIN_URL', 'https://app.cykube.net')


class BuildFailed(Exception):
    def __init__(self, reason: str):
        self.reason = reason


def get_screenshots_folder():
    return os.path.join(RESULTS_FOLDER, 'screenshots')


def get_videos_folder():
    return os.path.join(RESULTS_FOLDER, 'videos')


def init_build_dirs():
    shutil.rmtree('build', ignore_errors=True)
    if os.path.exists('dist.tgz'):
        os.remove('dist.tgz')
    os.chdir('build')
    os.makedirs(get_videos_folder())
    os.makedirs(get_screenshots_folder())


def fetch_dist(id: int, sha: str, timeout: int, hub_url: str, cache_url: str) -> TestRun:
    """
    Fetch the distribution from the cache server
    :param sha: commit SHA
    :param cache_url:
    :param hub_url:
    :param timeout:
    :param id: test run ID
    :return:
    """
    endtime = time() + timeout
    logging.info("Waiting for build")
    while time() < endtime:
        r = requests.get(f'{hub_url}/{id}')
        if r.status_code != 200:
            raise BuildFailed(f"Failed to contact hub: {r.status_code}")

        testrun = TestRun(**r.json())
        status = testrun.status
        if status == 'running':
            # fetch the dist
            r = requests.get(f'{cache_url}/{sha}.tgz', stream=True)
            with open('dist.tgz', 'wb') as outfile:
                shutil.copyfileobj(r.raw, outfile)

            # untar
            init_build_dirs()
            subprocess.run(['tar', 'xf', '../dist.tgz'])

            return testrun
        elif status != 'building':
            raise BuildFailed("Build failed or cancelled: quit")

        # otherwise sleep
        sleep(HUB_POLL_PERIOD)

    raise BuildFailed("Reached timeout - quitting")


def start_server(testrun: TestRun) -> subprocess.Popen:
    """
    Start the server
    :return:
    """
    proc = subprocess.Popen([testrun.server_cmd.split(' ')], shell=True)
    # wait until it's ready
    endtime = time() + 30
    logging.info("Waiting for server to be ready...")
    while True:
        r = requests.get(f'http://localhost:{testrun.server_port}')
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
        # add skipped
        for skipped in rawjson.get('pending', []):
            tests.append(TestResult(file=spec,
                                      title=skipped['title']))

        for test in rawjson['tests']:
            err = test.get('err')

            result = TestResult(file=spec,
                                title=test['title'],
                                status=TestResultStatus.failed if err else TestResultStatus.passed,
                                retry=test['currentRetry'],
                                duration=test['duration'],
                                started_at=started_at.isoformat(),
                                finished_at=datetime.datetime.now().isoformat())

            filename = os.path.split(spec)[-1]
            prefix = os.path.join(get_screenshots_folder(), filename)
            screenshot_files = list(os.listdir(prefix))
            failure_sshot = None
            manual_sshots = []
            for sshot in screenshot_files:
                if '(failed)' in sshot:
                    failure_sshot = sshot
                else:
                    manual_sshots.append(sshot)

            if manual_sshots:
                result.manual_screenshots = manual_sshots

            if err:
                # check for screenshots
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

                video_files = list(os.listdir(get_videos_folder()))
                if video_files:
                    # just pick the first one (should be only 1 surely?)
                    result.error.video = video_files[0]
            tests.append(result)

    return SpecResult(file=spec, tests=tests)


def get_cykube_session() -> requests.Session:
    mainhttp = requests.Session()
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    mainhttp.mount(CYKUBE_MAIN_URL, adapter)
    mainhttp.headers = {'Authorization': f'Bearer {TOKEN}'}
    return mainhttp


def run_cypress(file: str, timeout: int):
    subprocess.run(['../node_modules/.bin/cypress', 'run', '-s', file,
                    '--reporter=../json-reporter.js',
                    '-o', 'output=cykube/results/out.json',
                    '-c', f'screenshotsFolder={get_screenshots_folder()},screenshotOnRunFailure=true,'
                          f'video=true,videosFolder={get_videos_folder()}'],
                   timeout=timeout, check=True)


def upload_results(session: requests.Session, testrun_id, spec_id, result: SpecResult):
    files = []
    for test in result.results:
        if test.error:
            sshot = test.error.screenshot
            if sshot:
                fullpath = os.path.join(get_screenshots_folder(), sshot)
                files.append(('screenshot', (sshot, open(fullpath, 'rb'), 'image/png')))
            video = test.error.video
            if video:
                fullpath = os.path.join(get_videos_folder(), video)
                files.append(('video', (video, open(fullpath, 'rb'), 'video/mp4')))

    try:
        r = session.post(f'testrun/{testrun_id}/spec-completed/{spec_id}',
                          json=result.json(),
                          files=files)
        if not r.status_code == 200:
            raise BuildFailed(f'Test result post failed: {r.status_code}')
    except requests.RequestException:
        raise BuildFailed(f'Failed to contact Cykube server')


def run_tests(testrun: TestRun, hub_url: str, timeout: int):

    mainhttp = get_cykube_session()
    while True:
        r = requests.get(f'{hub_url}/testrun/{testrun.id}/next')
        if r.status_code == 204:
            # we're done
            break
        elif r.status_code == 200:
            # run the test
            spec = r.json()
            try:
                started_at = datetime.datetime.now()
                run_cypress(spec['file'], timeout)
                result = parse_results(started_at, spec['file'])
                upload_results(mainhttp, testrun.id, spec['id'], result)
                # cleanup
                shutil.rmtree(RESULTS_FOLDER, ignore_errors=True)

            except subprocess.CalledProcessError as ex:
                raise BuildFailed(f'Cypress run failed with return code {ex.returncode}')
            except subprocess.TimeoutExpired:
                raise BuildFailed("Exceeded run timeout")
        else:
            raise BuildFailed(f"Received unexpected status code from hub: {r.status_code}")
    mainhttp.close()


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('id', help='Test run ID')
    parser.add_argument('sha', help='Commit SHA')
    parser.add_argument('--timeout', required=False, type=int,
                        default=int(os.environ.get('BUILD_TIMEOUT', 30*60)),
                        help='Build timeout, in seconds')
    parser.add_argument('--hub-url', dest='hub', type=str,
                        default=os.environ.get('HUB_URL', 'http://127.0.0.1:5000'))
    parser.add_argument('--cache-url', dest='cache', type=str,
                        default=os.environ.get('HUB_URL', 'http://127.0.0.1:5001'))

    args = parser.parse_args()
    # fetch dist first
    testrun = fetch_dist(args.id, args.sha, args.timeout, args.hub, args.cache)
    # start the server
    proc = start_server(testrun)

    try:
        # now fetch specs until we're done or the build is cancelled
        run_tests(testrun, args.hub, args.timeout)
    except BuildFailed as ex:
        # TODO inform the server
        logging.error(ex.reason)
    finally:
        # kill the server
        proc.kill()

    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except Exception as ex:
        # bail out with an error - if we hit an OOM or similar we'll want to rerun the parent Job
        sys.exit(1)

