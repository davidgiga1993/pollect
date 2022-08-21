from __future__ import annotations

import time
from typing import Optional, List

from pollect.core import Helper
from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class HttpSource(Source):
    status_code: Optional[int] = None
    url: str | List[str] = ''
    proxy: Optional[str] = None

    def __init__(self, config):
        super().__init__(config)
        self.url = config.get('url')
        self.proxy = config.get('proxy')
        self.timeout = config.get('timeout', 10)
        self.status_code = config.get('statusCode')

    def _probe(self):
        if isinstance(self.url, list):
            data = ValueSet(labels=['url'])
            for url in self.url:
                value = self._probe_url(url)
                value.label_values = [url]
                data.add(value)
        else:
            data = ValueSet()
            data.add(self._probe_url(self.url))
        return data

    def _probe_url(self, url: str) -> Value:
        try:
            start = time.time() * 1000
            Helper.get_url(url, timeout=self.timeout, expected_status=self.status_code, proxy=self.proxy)
            end = time.time() * 1000
            return Value(int(end - start))
        except Exception as e:
            self.log.error(f'Could not probe {url}: {e}')
            return Value(self.timeout)
