import argparse
import sys
import time

import httpx
import sentry_sdk
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.redis import RedisIntegration

import builder
import cypress
from common.cloudlogging import configure_stackdriver_logging
from common.exceptions import BuildFailedException
from common.redisutils import sync_redis
from common.schemas import BuildFailureReport
from logs import logger
from settings import settings


def handle_sigterm_builder(signum, frame):
    """
    The builder can just exit with an error code: the parent Job will recreate up to the backoff limit
    """
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('command', choices=['clone', 'build', 'run'], help='Command')
    parser.add_argument('testrun_id', type=int, help='Test run ID')
    args = parser.parse_args()

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[RedisIntegration(), HttpxIntegration(), ], )

    # we'll need access to Redis
    try:
        sync_redis()
    except Exception as ex:
        logger.error(f"Failed to contact Redis ({ex}) - quitting")
        sys.exit(1)

    settings.init_build_dirs()

    client = None
    tstart = time.time()
    try:
        trid = args.testrun_id
        transport = httpx.HTTPTransport(retries=settings.MAX_HTTP_RETRIES)
        client = httpx.Client(transport=transport,
                              base_url=settings.MAIN_API_URL + f'/agent/testrun/{trid}',
                              headers={'Authorization': f'Bearer {settings.API_TOKEN}'})

        cmd = args.command
        configure_stackdriver_logging(f'cykube-{cmd}')
        if cmd == 'clone':
            builder.clone(trid)
        elif cmd == 'build':
            builder.build(trid)
        else:
            cypress.run(trid, client)
    except BuildFailedException as ex:
        logger.error(str(ex))
        duration = time.time() - tstart
        r = client.post('/build-failed', json=BuildFailureReport(msg=ex.msg,
                                                                 status_code=ex.status_code,
                                                                 duration=duration).dict())
        if r.status_code != 200:
            logger.error("Failed to contact cykubed servers to update status")
        sys.exit(1)

    finally:
        if client:
            client.close()


if __name__ == '__main__':
    main()
    sys.exit(0)
