from threading import Lock
from typing import Dict, List

from pollect.core.ValueSet import Value, AvgValue


class ValueCache:
    """
    Caches multiple values for async probing.
    If multiple values of the same name are available, their value can be averaged
    """

    def __init__(self):
        self._items: Dict[str, AvgValue] = {}
        self._lock = Lock()

    def flush_values(self) -> List[Value]:
        self._lock.acquire()
        out = []
        for item in self._items.values():
            base = item.base
            base.value = item.avg()
            out.append(base)
        self._items.clear()
        self._lock.release()
        return out

    def add(self, value: Value, average: bool = False):
        key = value.get_key()
        if average:
            if key in self._items:
                existing = self._items[key]
                existing.add(value)
                return

        self._items[key] = AvgValue(value)

    def lock(self):
        self._lock.acquire()

    def release(self):
        self._lock.release()
