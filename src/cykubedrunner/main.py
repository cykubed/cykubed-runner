import argparse
import os.path
import shutil
import sys
import time

import sentry_sdk
from sentry_sdk.integrations.httpx import HttpxIntegration

from cykubedrunner import builder, cypress
from cykubedrunner.app import app
from cykubedrunner.common.cloudlogging import configure_stackdriver_logging
from cykubedrunner.common.exceptions import BuildFailedException
from cykubedrunner.settings import settings
from cykubedrunner.utils import logger, log_build_failed_exception


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
            integrations=[HttpxIntegration(), ], )

    cmd = args.command
    if cmd == 'build':
        # in case this is a retry, make sure the build directory is clean
        if os.path.exists(settings.src_dir):
            shutil.rmtree(settings.src_dir)

    settings.init_build_dirs()

    trid = args.testrun_id
    app.init_http_client(trid)
    exit_code = 0

    try:
        configure_stackdriver_logging(f'cykubed-{cmd}')
        if cmd == 'build':
            builder.build(trid)
        elif cmd == 'prepare_cache':
            builder.prepare_cache()
        else:
            cypress.run(trid)

    except BuildFailedException as ex:
        logger.error(f'{cmd.capitalize()} failed: {ex}')
        # tell the agent
        log_build_failed_exception(trid, ex)

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
