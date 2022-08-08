from typing import TypeVar, Dict

T = TypeVar('T')
K = TypeVar('K')


def put_if_absent(dict_obj: Dict[K, T], key: any, value: T) -> T:
    """
    Returns the value from key
    :param dict_obj:
    :param key:
    :param value:
    :return:
    """
    if key in dict_obj:
        return dict_obj[key]
    dict_obj[key] = value
    return value
