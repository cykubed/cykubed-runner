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
        # we'll need the test run from the agent
        try:
            tr = NewTestRun.parse_raw(httpx.get(f'{settings.AGENT_URL}/testrun/{args.testrun_id}').text)
        except:
            logger.exception("Failed to fetch test run from agent: quitting")
            sys.exit(1)

        if cmd == 'build':
            try:
                build.clone_and_build(tr)
            except Exception:
                logger.exception("Build failed")
                build.post_status(tr.id, 'failed')
                # sleep(3600)
                sys.exit(1)
        else:
            if not tr.cache_key:
                logger.error("Missing cache key: quitting")
                sys.exit(1)
            try:
                cypress.start(args.testrun_id, tr.cache_key)
            except:
                logger.exception("Cypress run failed")
                sys.exit(1)


if __name__ == '__main__':
    main()
