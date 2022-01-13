from typing import Optional
from urllib import request
from urllib.error import HTTPError


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


def get_url(url, timeout: int = 5, expected_status: Optional[int] = None):
    try:
        with request.urlopen(url, timeout=timeout) as url:
            return url.read()
    except HTTPError as e:
        if expected_status == e.status:
            return e.read()
        raise e
