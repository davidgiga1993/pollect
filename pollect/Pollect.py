import argparse
import json
import signal
import sys

from pollect.core.Core import Configuration
from pollect.core.ExecutionScheduler import ExecutionScheduler
from pollect.core.Log import Log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', dest='debug', action='store_true')
    parser.add_argument('-c', '--config', dest='config',
                        help='Configuration file which should be read')
    parser.add_argument('-r', '--dry-run', dest='dry_run', action='store_true',
                        help='Prints the probed data to the stdout instead of sending it to the writer')
    args = parser.parse_args()

    if args.debug:
        Log.set_debug()

    def signal_handler(signal, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    with open(args.config, 'r') as f:
        raw_config = json.load(f)

    config = Configuration(raw_config, args.dry_run)
    scheduler = ExecutionScheduler(config, config.create_executors())
    scheduler.create()
    scheduler.run()


if __name__ == '__main__':
    main()
