import argparse
import asyncio
import sys

import httpx
from loguru import logger

import build
import cypress
from common.utils import get_headers
from settings import settings


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('command', choices=['build', 'run'])
    parser.add_argument('id', help='Test run ID')
    parser.add_argument('--loglevel', default='info', help='Log level')

    args = parser.parse_args()

    cmd = args.command

    def publish(message):
        r = httpx.post(f'{settings.MAIN_API_URL}/agent/testrun/{args.id}/logs',
                       data=message, headers=get_headers())
        if r.status_code != 200:
            logger.error(f"Failed to push logs to server: {r.text}")

    fmt = "{time} {level} {message}"
    logger.add(publish, level="INFO", format=fmt)
    logger.add(sys.stderr, level=args.loglevel.upper(), format=fmt)

    if cmd == 'build':
        try:
            asyncio.run(build.clone_and_build(args.id))
        except Exception:
            logger.exception("Build failed")
            build.post_status(args.id, 'failed')
            sys.exit(1)
    else:
        try:
            asyncio.run(cypress.start(args.id))
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
        print(ex)
        sys.exit(1)
