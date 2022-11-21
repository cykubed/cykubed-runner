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


class BuildCancelled(Exception):
    pass


def init_build_dirs():
    shutil.rmtree('build', ignore_errors=True)
    if os.path.exists('dist.tgz'):
        os.remove('dist.tgz')
    os.makedirs('build/cypress/results/json')
    os.makedirs('build/cypress/screenshots')


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
            raise BuildCancelled()

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
            raise BuildCancelled()

        # otherwise sleep
        sleep(HUB_POLL_PERIOD)

    logging.info("Reached timeout - quitting")
    raise BuildCancelled()


def start_server():
    """
    Start the server
    :return:
    """



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
    fetch_dist(args.id, args.sha, args.timeout, args.hub, args.cache)
    # now start the server
    start_server()


if __name__ == '__main__':
    try:
        main()
    except Exception as ex:
        # bail out with an error
        sys.exit(1)

