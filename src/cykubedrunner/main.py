import argparse
import sys
import time
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.redis import RedisIntegration
import sentry_sdk

from cykubedrunner.common.cloudlogging import configure_stackdriver_logging
from cykubedrunner.common.exceptions import BuildFailedException
from cykubedrunner.common.redisutils import sync_redis
from cykubedrunner.common.schemas import TestRunErrorReport, AgentTestRunErrorEvent

from cykubedrunner import builder, cypress
from cykubedrunner.settings import settings
from cykubedrunner.utils import send_agent_event, logger


def handle_sigterm_builder(signum, frame):
    """
    The builder can just exit with an error code: the parent Job will recreate up to the backoff limit
    """
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser('Cykubed Runner')
    parser.add_argument('command', choices=['build', 'prepare_cache', 'run'], help='Command')
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

    trid = args.testrun_id
    exit_code = 0

    try:
        cmd = args.command
        configure_stackdriver_logging(f'cykubed-{cmd}')
        if cmd == 'build':
            builder.build(trid)
        elif cmd == 'prepare_cache':
            builder.prepare_cache(trid)
        else:
            cypress.run(trid)

    except BuildFailedException as ex:
        logger.error(f'Build failed: {ex}')
        # tell the agent
        send_agent_event(AgentTestRunErrorEvent(testrun_id=trid,
                                                report=TestRunErrorReport(msg=ex.msg,
                                                                          stage=ex.stage,
                                                                          error_code=ex.status_code)))
        if settings.KEEPALIVE_ON_FAILURE:
            time.sleep(3600)
    except Exception as ex:
        logger.exception(f'Build failed: {ex}')
        if settings.KEEPALIVE_ON_FAILURE:
            time.sleep(3600)
        exit_code = 1
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
