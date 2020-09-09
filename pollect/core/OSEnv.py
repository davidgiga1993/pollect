import platform

WINDOWS = 1
LINUX = 2
CURRENT_PLATFORM = -1


def __init_os():
    global CURRENT_PLATFORM
    if CURRENT_PLATFORM != -1:
        return
    uname = platform.system()
    if 'Windows' in uname:
        CURRENT_PLATFORM = WINDOWS
    else:
        CURRENT_PLATFORM = LINUX


def is_linux():
    """
    Checks if the current OS is linux based

    :return: True if linux, false if other
    :rtype: bool
    """
    return CURRENT_PLATFORM == LINUX


__init_os()
