import argparse
import sys
from time import sleep

import build
import cypress
from common.exceptions import BuildFailedException
from logging import logger


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('--loglevel', default='info', help='Log level')

    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    build_parser = subparsers.add_parser('build')
    build_parser.add_argument('project_id', help='Project ID')
    build_parser.add_argument('local_id', help='Test run local ID')

    run_parser = subparsers.add_parser('run')
    run_parser.add_argument('project_id', help='Project ID')
    run_parser.add_argument('local_id', help='Test run local ID')
    run_parser.add_argument('cache_key', help='Node cache key')

    args = parser.parse_args()

    cmd = args.command

    try:
        logger.init(args.project_id, args.local_id, source=cmd, level=args.loglevel)

        if cmd == 'shell':
            sleep(3600*24)
            sys.exit(0)
        elif cmd == 'build':
            build.clone_and_build(args.project_id, args.local_id)
        else:
            cypress.start(args.project_id, args.local_id, args.cache_key)
        return
    except BuildFailedException as ex:
        build.post_status(args.project_id, args.local_id, 'failed')
        sys.exit(1)
    except Exception:
        logger.exception(f"{cmd.capitalize()} failed")
        build.post_status(args.project_id, args.local_id, 'failed')
        sys.exit(1)


if __name__ == '__main__':
    main()
