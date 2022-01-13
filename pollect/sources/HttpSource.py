import time
from typing import Optional

from pollect.core import Helper
from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class HttpSource(Source):
    status_code: Optional[int] = None

    def __init__(self, config):
        super().__init__(config)
        self.url = config.get('url')
        self.timeout = config.get('timeout', 10)
        self.status_code = config.get('statusCode')

    def _probe(self):
        data = ValueSet()
        try:
            start = time.time() * 1000
            Helper.get_url(self.url, timeout=self.timeout, expected_status=self.status_code)
            end = time.time() * 1000
            data.add(Value(int(end - start)))
        except Exception as e:
            self.log.error('Could not probe ' + str(e))
            data.add(Value(self.timeout))
        return data
