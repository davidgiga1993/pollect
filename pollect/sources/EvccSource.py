import json
import re
from contextlib import closing
from typing import Optional, List, Dict

from websocket import create_connection

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class EvccSource(Source):
    _host: str
    LP_PREFIX = 'loadpoints.'

    def __init__(self, config):
        super().__init__(config)
        self._host = config['host']

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        # Use a new connection every time since we don't care about
        # events
        data = self._get_data()

        other_metrics = ValueSet()
        loadpoint = ValueSet(labels=['title'])

        # Find loadpoint names and indices
        loadpoint_names: Dict[int, str] = {}
        for key, value in data.items():
            if key.startswith(self.LP_PREFIX):
                index = self._get_index(key)
                loadpoint_names[index] = data.get(f'{self.LP_PREFIX}{index}.title')

        # Now parse the values
        for key, value in data.items():
            if not self._is_metric(value):
                continue

            if key.startswith(self.LP_PREFIX):
                index = self._get_index(key)
                name = loadpoint_names[index]
                value_name = key.replace(f'{self.LP_PREFIX}{index}.', '')
                loadpoint.add(Value(value, [name], value_name))
                continue

            # Not a loadpoint
            other_metrics.add(Value(value, name=key))

        return [loadpoint, other_metrics]

    def _get_data(self) -> Dict[str, any]:
        with closing(create_connection(f'ws://{self._host}/ws')) as conn:
            data = conn.recv()
            return json.loads(data)

    @staticmethod
    def _get_index(key: str) -> int:
        match = re.match(r'.+?\.(\d+)\..+', key)
        if not match:
            return 0
        return match.group(1)

    def _is_metric(self, value: any) -> bool:
        return isinstance(value, float) or isinstance(value, int) or isinstance(value, bool)
