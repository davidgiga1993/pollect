import sys


def error(msg):
    sys.stderr.write('[E] ' + msg)


def info(msg):
    print('[I] ' + msg)


def warning(msg):
    print('[W] ' + msg)
