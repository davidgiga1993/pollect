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


def get_url(url, timeout: int = 5, expected_status: Optional[int] = None, proxy: Optional[str] = None):
    try:
        req = request.Request(url)
        if proxy is not None:
            req.set_proxy(proxy, 'http')
            req.set_proxy(proxy, 'https')
        req.timeout = timeout

        with request.urlopen(req) as url:
            status_code = url.getcode()
            if expected_status is None:
                # Accept any "ok" status
                if status_code < 200 or status_code >= 300:
                    raise ValueError(f'Invalid status code {status_code}')
                elif status_code != expected_status:
                    raise ValueError(f'Invalid status code {status_code}')
            content = url.read()
            return content
    except HTTPError as e:
        if expected_status is None and expected_status == e.status:
            return e.read()
        raise e
