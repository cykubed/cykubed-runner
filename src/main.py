import argparse
import sys
from time import sleep

import httpx

import build
import cypress
from common.schemas import NewTestRun
from common.settings import settings
from logs import logger


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('--loglevel', default='info', help='Log level')
    parser.add_argument('command', choices=['shell', 'build', 'run'], help='Command')
    parser.add_argument('testrun_id', help='Test run ID')

    args = parser.parse_args()

    cmd = args.command
    if cmd == 'shell':
        sleep(3600*24)
        sys.exit(0)
    else:
        if cmd == 'build':
            try:
                build.clone_and_build(args.testrun_id)
            except Exception:
                logger.exception("Build failed")
                build.post_status(args.testrun_id, 'failed')
                # sleep(3600)
                sys.exit(1)
        else:
            try:
                cypress.start(args.testrun_id)
            except:
                logger.exception("Cypress run failed")
                sys.exit(1)
                # sleep(300)


if __name__ == '__main__':
    main()
    sys.exit(0)
