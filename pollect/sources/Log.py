import sys


def error(msg):
    sys.stderr.write('[E] ' + msg)
    sys.stderr.flush()


def info(msg):
    print('[I] ' + msg)
    sys.stdout.flush()


def warning(msg):
    print('[W] ' + msg)
    sys.stdout.flush()
