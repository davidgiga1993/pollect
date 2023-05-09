from typing import Optional
from urllib.parse import urlparse

import requests


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
    proxies = None
    if proxy == '':
        parsed = urlparse(url)
        proxies = {
            'no_proxy': parsed.hostname
        }
    elif proxy is not None:
        proxies = {
            'http': proxy,
            'https': proxy
        }

    response = requests.get(url, timeout=(timeout, timeout), proxies=proxies)
    status_code = response.status_code
    if expected_status is None:
        # Accept any "ok" status
        if status_code < 200 or status_code >= 300:
            raise ValueError(f'Invalid status code {status_code}')
    elif status_code != expected_status:
        raise ValueError(f'Invalid status code {status_code}')
    return response.text
