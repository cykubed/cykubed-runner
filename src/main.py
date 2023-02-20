import argparse
import sys
from time import sleep

import build
import cypress
from common.exceptions import BuildFailedException
from common.utils import decode_testrun
from logs import logger


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('--loglevel', default='info', help='Log level')

    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    build_parser = subparsers.add_parser('build')
    build_parser.add_argument('testrun', help='Base64-encoded NewTestRun')

    run_parser = subparsers.add_parser('run')
    run_parser.add_argument('testrun_id', help='Test run ID')
    run_parser.add_argument('cache_key', help='Node cache key')

    args = parser.parse_args()

    cmd = args.command
    if cmd == 'shell':
        sleep(3600*24)
        sys.exit(0)
    elif cmd == 'build':
        tr = None
        try:
            tr = decode_testrun(args.testrun.strip())
            build.clone_and_build(tr)
        except Exception:
            logger.exception("Build failed")
            if tr:
                build.post_status(tr.id, 'failed')
            sys.exit(1)
    else:
        try:
            cypress.start(args.testrun_id, args.cache_key)
        except:
            logger.exception("Cypress run failed")
            sys.exit(1)


if __name__ == '__main__':
    main()
