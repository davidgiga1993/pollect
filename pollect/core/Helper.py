from urllib import request


def remove_empty_list(list_obj):
    if list_obj is None:
        return None
    if len(list_obj) == 0:
        return None

    return list_obj


def accept(include, exclude, value):
    if exclude is not None and value in exclude:
        return False
    if include is not None and value not in include:
        return False
    return True


def get_url(url, timeout: int = 5):
    with request.urlopen(url, timeout=timeout) as url:
        return url.read()
