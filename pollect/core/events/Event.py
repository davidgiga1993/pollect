from __future__ import annotations
from typing import List, Callable


class Event:
    """
    Standalone event
    """
    _listener: List[Callable]

    def __init__(self):
        self._listener = []

    def fire(self, *args, **kwargs):
        for call in self._listener:
            call(*args, **kwargs)

    def __add__(self, method: Callable) -> Event:
        self._listener.append(method)
        return self

    def __sub__(self, method: Callable) -> Event:
        self._listener.remove(method)
        return self
