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
from common.enums import AgentEventType
from common.exceptions import BuildFailedException, RunFailedException
from common.redisutils import sync_redis
from common.schemas import BuildFailureReport, AgentEvent
from settings import settings
from utils import send_agent_event, logger


def handle_sigterm_builder(signum, frame):
    """
    The builder can just exit with an error code: the parent Job will recreate up to the backoff limit
    """
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('command', choices=['dummy', 'clone', 'build', 'run'], help='Command')
    parser.add_argument('testrun_id', type=int, help='Test run ID')
    args = parser.parse_args()

    if args.command == 'dummy':
        with open('/build/test.txt', 'w') as f:
            f.write('fish!')
        return

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
    trid = args.testrun_id
    try:
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
    except RunFailedException as ex:
        logger.error(str(ex))
        sys.exit(1)

    except BuildFailedException as ex:
        logger.error(f'Build failed: {ex}')
        time.sleep(3600)
        duration = time.time() - tstart
        r = client.post('/build-failed', json=BuildFailureReport(msg=ex.msg,
                                                                 status_code=ex.status_code,
                                                                 duration=duration).dict())
        if r.status_code != 200:
            logger.error("Failed to contact cykubed servers to update status")
        # tell the agent
        send_agent_event(AgentEvent(type=AgentEventType.run_completed,
                                    testrun_id=trid))
        sys.exit(0)
    except Exception as ex:
        logger.exception(f'Build failed: {ex}')
        time.sleep(3600)
        sys.exit(1)
    finally:
        if client:
            client.close()


if __name__ == '__main__':
    main()
    sys.exit(0)
