import logging
import sys


class ColorFormatter(logging.Formatter):
    grey = '\x1b[38;21m'
    yellow = '\x1b[33;21m'
    red = '\x1b[31;21m'
    bold_red = '\x1b[31;1m'
    reset = '\x1b[0m'
    format = '%(levelname)-.1s %(asctime)-.19s [%(name)s] %(message)s'

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class Log:
    log_level = logging.INFO

    def __init__(self, name: str = None):
        if not hasattr(self, 'log'):
            if name is None:
                name = self.__class__.__name__
            log = logging.getLogger(name)
            log.setLevel(Log.log_level)
            self.log = log

    @classmethod
    def set_level(cls, log_level: str):
        if log_level == 'debug':
            cls.log_level = logging.DEBUG
        elif log_level == 'info':
            cls.log_level = logging.INFO
        elif log_level == 'warning':
            cls.log_level = logging.WARNING
        elif log_level == 'error':
            cls.log_level = logging.ERROR

    @classmethod
    def setup(cls):
        log = logging.root
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(ColorFormatter())
        log.handlers.clear()
        log.addHandler(handler)
