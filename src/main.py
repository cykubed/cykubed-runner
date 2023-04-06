import argparse
import asyncio
import sys

import httpx
import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.redis import RedisIntegration

import build
import cypress
from common.cloudlogging import configure_stackdriver_logging
from common.db import async_redis
from common.settings import settings
from logs import logger


def handle_sigterm_builder(signum, frame):
    """
    The builder can just exit with an error code: the parent Job will recreate up to the backoff limit
    """
    sys.exit(1)


async def run(args):
    client = None
    try:
        trid = args.testrun_id
        transport = httpx.AsyncHTTPTransport(retries=settings.MAX_HTTP_RETRIES)
        client = httpx.AsyncClient(transport=transport,
                                   base_url=settings.MAIN_API_URL+f'/agent/testrun/{trid}',
                                   headers={'Authorization': f'Bearer {settings.API_TOKEN}'})

        cmd = args.command
        if cmd == 'build':
            await build.run(trid, client)
        else:
            configure_stackdriver_logging('cykube-runner')
            await cypress.run(trid, client)
    finally:
        if client:
            await client.aclose()


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('command', choices=['build', 'run'], help='Command')
    parser.add_argument('testrun_id', type=int, help='Test run ID')

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[RedisIntegration(), AsyncioIntegration(), HttpxIntegration(),], )

    # we'll need access to Redis
    try:
        async_redis()
    except Exception as ex:
        logger.error(f"Failed to contact Redis ({ex}) - quitting")
        sys.exit(1)

    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
    sys.exit(0)
