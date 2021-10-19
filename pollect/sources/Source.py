from __future__ import annotations

import os
import time
import typing
from abc import abstractmethod
from typing import Optional, List

from pollect.core import OSEnv, Helper
from pollect.core.Log import Log
from pollect.core.ValueSet import ValueSet, Value

if typing.TYPE_CHECKING:
    from pollect.core.Core import Configuration


class Source(Log):
    type: str = None

    name: Optional[str] = None
    """
    Name of this source, may be used as value name prefix
    """

    global_conf: Configuration

    def __init__(self, config):
        super().__init__(config['type'])
        self.name = config.get('name')
        self.type = config['type']

    def setup(self, global_conf):
        """
        Initializes the source

        :param global_conf: Global configuration
        :type global_conf: Configuration
        """
        self.global_conf = global_conf

    def probe(self) -> Optional[List[ValueSet]]:
        """
        Probes the data and returns it

        :return: Single value or dict of values where the key is appendix for the data path
        """
        results = self._probe()
        if results is None:
            return None
        if isinstance(results, ValueSet):
            results = [results]
        for result in results:
            result.name = self._get_suffix()
        return results

    @abstractmethod
    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        """
        Probes the data and returns it

        :return: Single value or dict of values where the key is appendix for the data path
        """

    def _get_suffix(self) -> str:
        """
        Returns the suffix which should be added
        to all values for this data source

        :return: Path
        """
        if self.name is None:
            return self.type
        return self.type + '.' + self.name

    def __str__(self):
        return self._get_suffix()


class DummySource(Source):
    def __init__(self, config):
        super().__init__(config)
        self.value = config.get('value')

    def _probe(self) -> Optional[ValueSet]:
        data = ValueSet()
        data.add(Value(self.value))
        return data


class HttpSource(Source):
    def __init__(self, config):
        super().__init__(config)
        self.url = config.get('url')
        self.timeout = config.get('timeout', 10)

    def _probe(self):
        data = ValueSet()
        try:
            start = time.time() * 1000
            Helper.get_url(self.url, timeout=self.timeout)
            end = time.time() * 1000
            data.add(Value(int(end - start)))
        except Exception as e:
            self.log.error('Could not probe ' + str(e))
            data.add(Value(self.timeout))
        return data


class LoadAvgSource(Source):
    def _probe(self):
        if not OSEnv.is_linux():
            return None
        short, mid, long = os.getloadavg()

        data = ValueSet(labels=['time'])
        data.add(Value(short, label_values=['short']))
        data.add(Value(mid, label_values=['mid']))
        data.add(Value(long, label_values=['long']))
        return data
