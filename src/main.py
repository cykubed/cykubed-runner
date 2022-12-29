import argparse
import asyncio
import logging
import sys

import clone
import run
from utils import start_log_thread


def main():
    parser = argparse.ArgumentParser('CykubeRunner')
    parser.add_argument('command', choices=['build', 'run'])
    parser.add_argument('id', help='Test run ID')
    parser.add_argument('--loglevel', default='info', help='Log level')

    args = parser.parse_args()

    cmd = args.command

    logfile = start_log_thread(args.id)
    logging.basicConfig(filename=logfile.name,
                        encoding='utf-8',
                        format='%(levelname)s: %(message)s',
                        level=logging.getLevelName(args.loglevel.upper()))

    if cmd == 'build':
        asyncio.run(clone.clone_and_build(args.id))
    else:
        asyncio.run(run.start(args.id))


if __name__ == '__main__':
    try:
        main()
        sys.exit(0)
    except Exception as ex:
        # bail out with an error - if we hit an OOM or similar we'll want to rerun the parent Job
        print(ex)
        sys.exit(1)
