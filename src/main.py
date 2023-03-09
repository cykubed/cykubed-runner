import argparse

import common.utils
import mongo
import os
import sys
from time import sleep

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration

import build
import cypress
import utils
from common.exceptions import BuildFailedException, MongoConnectionException
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
        # we'll need access to MongoDB
        try:
            common.utils.ensure_mongo_connection()
        except MongoConnectionException:
            logger.error("Failed to connect to MongoDB: bailing out")
            sys.exit(1)

        if cmd == 'build':
            try:
                build.clone_and_build(args.testrun_id)
            except Exception:
                logger.exception("Build failed")
                mongo.update_status(args.testrun_id, 'failed')
                # sleep(3600)
                sys.exit(1)
        else:
            try:
                cypress.start(args.testrun_id)
            except BuildFailedException:
                logger.exception("Cypress run failed")
                mongo.update_status(args.testrun_id, 'failed')
                sys.exit(1)
            except Exception as ex:
                logger.exception("Cypress run crashs")
                sleep(3600)


if __name__ == '__main__':
    main()
    sys.exit(0)
