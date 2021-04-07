import os
import time
from abc import abstractmethod
from typing import Optional, List

from pollect.core import OSEnv, Helper
from pollect.core.ValueSet import ValueSet, Value
from pollect.sources import Log


class Source:
    type: str = None
    name: Optional[str] = None

    def __init__(self, config):
        self.name = config.get('name')
        self.type = config['type']
        self.global_conf = None
        """
        Global configuration

        :type global_conf: Configuration
        """

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
            Log.error('Could not probe ' + str(e))
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
