import argparse
import asyncio
import os
import sys
from time import sleep

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration

import build
import cypress
from common.db import redis
from logs import logger


def handle_sigterm_builder(signum, frame):
    """
    The builder can just exit with an error code: the parent Job will recreate up to the backoff limit
    """
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('--loglevel', default='info', help='Log level')
    parser.add_argument('command', choices=['shell', 'build', 'run'], help='Command')
    parser.add_argument('testrun_id', type=int, help='Test run ID')

    args = parser.parse_args()

    if os.environ.get('SENTRY_DSN'):
        sentry_sdk.init(integrations=[
            HttpxIntegration(),
            AsyncioIntegration(),
        ], )

    cmd = args.command

    if cmd == 'shell':
        sleep(3600*24)
        sys.exit(0)
    else:
        # we'll need access to Redis
        try:
            redis()
        except Exception as ex:
            logger.error(f"Failed to contact Redis ({ex}) - quitting")
            sys.exit(1)

        if cmd == 'build':
            asyncio.run(build.run(args.testrun_id))
        else:
            asyncio.run(cypress.run(args.testrun_id))


if __name__ == '__main__':
    main()
    sys.exit(0)
