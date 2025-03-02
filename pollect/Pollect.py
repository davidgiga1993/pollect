import argparse
import json
import signal
import sys
from typing import Dict

import yaml

from pollect.core.Core import Configuration
from pollect.core.ExecutionScheduler import ExecutionScheduler
from pollect.core.Log import Log
from pollect.libs.DependencyResolver import DependencyResolver


def load_config(config: str) -> Dict[str, any]:
    if config.endswith('.json'):
        with open(config, 'r') as f:
            return json.load(f)
    if config.endswith('.yml'):
        with open(config, 'r') as f:
            return yaml.safe_load(f)

    # File has an unknown or no extension, try all supported formats
    try:
        return load_config(config + '.yml')
    except FileNotFoundError:
        return load_config(config + '.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', dest='version', action='store_true',
                        help='Prints the current version')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='Shortcut for --log-level debug')
    parser.add_argument('--log-level', dest='log_level', default='info',
                        choices=['info', 'debug', 'warning', 'error'],
                        help="Sets the log level, info by default (if --debug isn't set)")
    parser.add_argument('-c', '--config', dest='config', default='config',
                        help='Configuration file which should be read. If no file extension is given '
                             'both (yml and json) will be checked.')
    parser.add_argument('--dependencies', dest='dependencies', action='store_true',
                        help='Prints all required dependencies for the given configuration in a requirements.txt format')
    parser.add_argument('-r', '--dry-run', dest='dry_run', action='store_true',
                        help='Prints the probed data to stdout instead of sending it to the writer')
    args = parser.parse_args()

    if args.version:
        from pollect import __version__
        print(f'Pollect {__version__}')
        return

    log_level = args.log_level
    if args.debug:
        log_level = 'debug'
    Log.setup()
    Log.set_level(log_level)

    scheduler = None

    def signal_handler(signal, frame):
        nonlocal scheduler
        if scheduler is not None:
            scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    raw_config = load_config(args.config)
    config = Configuration(raw_config, args.dry_run)
    if args.dependencies:
        DependencyResolver(config).print()
        return

    scheduler = ExecutionScheduler(config, config.create_executors())
    scheduler.create()
    scheduler.run()


if __name__ == '__main__':
    main()
