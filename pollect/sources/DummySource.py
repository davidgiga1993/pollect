import threading
from time import sleep
from typing import Optional

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class DummySource(Source):
    def __init__(self, config):
        super().__init__(config)
        self.value = config.get('value')
        self.sleep_time = config.get('sleep', 0)
        self.callback = config.get('callback', None)

    def _probe(self) -> Optional[ValueSet]:
        if self.sleep_time > 0:
            sleep(self.sleep_time)
        data = ValueSet()
        data.add(Value(self.value))
        if self.callback is not None:
            threading.Thread(target=self.callback).start()
            self.callback = None
        return data
