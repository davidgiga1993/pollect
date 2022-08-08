from __future__ import annotations

import os
import typing
from abc import abstractmethod
from time import sleep
from typing import Optional, List

from pollect.core import OSEnv
from pollect.core.Log import Log
from pollect.core.ValueSet import ValueSet, Value

if typing.TYPE_CHECKING:
    from pollect.core.Core import Configuration


class Source(Log):
    """
    A single metrics source. May return multiple metrics and labels
    """

    type: str = None
    """
    Type string of this source
    """

    name: Optional[str] = None
    """
    Name of this source, may be used as value name prefix
    """

    labels: typing.Dict[str, str] = {}
    """
    Static labels which should be added to all values
    """

    global_conf: Configuration

    def __init__(self, config):
        super().__init__(config['type'])
        self.name = config.get('name')

        self.labels = config.get('labels', {})
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

            # Add static labels from config
            result.labels.extend(self.labels.keys())
            for value in result.values:
                value.label_values.extend(self.labels.values())

        return results

    def shutdown(self):
        """
        Terminates any background jobs running for this source
        """
        pass

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
        self.sleep = config.get('sleep', 0)

    def _probe(self) -> Optional[ValueSet]:
        if self.sleep > 0:
            sleep(self.sleep)
        data = ValueSet()
        data.add(Value(self.value))
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
