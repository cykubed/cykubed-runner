import argparse
import subprocess
import logging
import os
import sys
from time import time, sleep
import shutil

import requests

from common.schemas import TestRun

HUB_POLL_PERIOD = int(os.environ.get('HUB_POLL_PERIOD', 10))


class BuildFailed(Exception):
    def __init__(self, reason=False):
        self.reason = reason


def init_build_dirs():
    shutil.rmtree('build', ignore_errors=True)
    if os.path.exists('dist.tgz'):
        os.remove('dist.tgz')
    os.makedirs('build/cykube/results/json')
    os.makedirs('build/cykube/results/screenshots')


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
            logging.error(f"Failed to contact hub: {r.status_code}")
            raise BuildFailed()

        testrun = TestRun(**r.json())
        status = testrun.status
        if status == 'running':
            init_build_dirs()
            # fetch the dist
            r = requests.get(f'{cache_url}/{sha}.tgz', stream=True)
            with open('dist.tgz', 'wb') as outfile:
                shutil.copyfileobj(r.raw, outfile)

            # untar
            os.chdir('build')
            subprocess.run(['tar', 'xf', '../dist.tgz'])

            return testrun
        elif status != 'building':
            logging.info("Build failed or cancelled: quit")
            raise BuildFailed()

        # otherwise sleep
        sleep(HUB_POLL_PERIOD)

    logging.info("Reached timeout - quitting")
    raise BuildFailed()


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
                logging.error('Failed to start server')
                raise BuildFailed()
            sleep(5)
        else:
            return proc


def run_tests(testrun: TestRun, hub_url: str, timeout: int):
    while True:
        r = requests.get(f'{hub_url}/testrun/{testrun.id}/next')
        if r.status_code == 204:
            # we're done
            return
        elif r.status_code == 200:
            # run the test
            spec = r.json()
            try:
                subprocess.run(['../node_modules/.bin/cypress', 'run', '-s', spec['file'],
                                '--reporter=../json-reporter.js',
                                '-o', 'output=cykube/results/json',
                                '-c', 'screenshotsFolder=cykube/results/screenshots,screenshotOnRunFailure=true'],
                               timeout=timeout, check=True)
                # TODO report report to hub and cleanup

            except subprocess.CalledProcessError as ex:
                raise BuildFailed(f'Cypress run failed with return code {ex.returncode}')
            except subprocess.TimeoutExpired:
                raise BuildFailed("Exceeded run timeout")
        else:
            raise BuildFailed(f"Received unexpected status code from hub: {r.status_code}")


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
        # TODO inform the hub
        logging.error(ex.reason)
    finally:
        # kill the server
        proc.kill()

    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except Exception as ex:
        # bail out with an error
        sys.exit(1)

