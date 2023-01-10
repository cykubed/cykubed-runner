import argparse
import sys
from time import sleep

from loguru import logger

import build
import cypress
import logs
from common import k8common
from settings import settings


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('--loglevel', default='info', help='Log level')

    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    build_parser = subparsers.add_parser('build')
    build_parser.add_argument('id', help='Test run ID')

    run_parser = subparsers.add_parser('run')
    run_parser.add_argument('id', help='Test run ID')
    run_parser.add_argument('sha', help='SHA')

    args = parser.parse_args()

    cmd = args.command

    k8common.init()

    fmt = "{time:HH:mm:ss.SSS} (" + cmd + ") {level} {message}"
    handler = logs.PublishLogHandler(args.id, settings.LOG_UPDATE_PERIOD)
    logger.add(handler,
               level=args.loglevel.upper(), format=fmt)

    if cmd == 'shell':
        sleep(3600*24)
        sys.exit(0)

    if cmd == 'build':
        try:
            build.clone_and_build(args.id)
        except Exception:
            logger.exception("Build failed - bailing out")
            build.post_status(args.id, 'failed')
            sys.exit(1)
    else:
        try:
            cypress.start(args.id, args.sha)
        except Exception:
            logger.exception("Run failed")
            build.post_status(args.id, 'failed')
            sys.exit(1)


if __name__ == '__main__':
    try:
        main()
        sys.exit(0)
    except Exception as ex:
        # bail out with an error - if we hit an OOM or similar we'll want to rerun the parent Job
        logger.exception(f"Failed: {ex}")
        sys.exit(1)
