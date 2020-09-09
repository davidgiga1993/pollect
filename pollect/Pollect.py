import argparse
import json
import signal
import sys

from pollect.core.Core import Configuration
from pollect.core.Events import EventBus
from pollect.core.ExecutionScheduler import ExecutionScheduler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config',
                        help='Configuration file which should be read')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true',
                        help='Prints the probed data to the stdout instead of sending it to the writer')
    args = parser.parse_args()

    EventBus.instance()

    def signal_handler(signal, frame):
        EventBus.instance().sigint.fire()
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
