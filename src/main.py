import argparse
import sys
import time

import httpx
import sentry_sdk
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.redis import RedisIntegration

import builder
import cypress
from app import app
from common.cloudlogging import configure_stackdriver_logging
from common.enums import AgentEventType
from common.exceptions import BuildFailedException, RunFailedException
from common.redisutils import sync_redis
from common.schemas import TestRunFailureReport, AgentEvent, AgentTestRunFailedEvent
from settings import settings
from utils import send_agent_event, logger


def handle_sigterm_builder(signum, frame):
    """
    The builder can just exit with an error code: the parent Job will recreate up to the backoff limit
    """
    sys.exit(1)


def main() -> int:
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
    exit_code = 0

    try:
        cmd = args.command
        configure_stackdriver_logging(f'cykube-{cmd}')
        if cmd == 'clone':
            builder.clone(trid)
        elif cmd == 'build':
            builder.build(trid)
        else:
            cypress.run(trid)

    except BuildFailedException as ex:
        logger.error(f'Build failed: {ex}')
        duration = time.time() - tstart
        # tell the agent
        send_agent_event(AgentTestRunFailedEvent(testrun_id=trid, report=TestRunFailureReport(msg=ex.msg,
                                                                                              stage=ex.stage,
                                                                                              status_code=ex.status_code,
                                                                                              duration=duration)))
        if settings.KEEPALIVE_ON_FAILURE:
            time.sleep(3600)
    except Exception as ex:
        logger.exception(f'Build failed: {ex}')
        if settings.KEEPALIVE_ON_FAILURE:
            time.sleep(3600)
        exit_code = 1
    finally:
        if client:
            client.close()
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
