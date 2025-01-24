import requests
from typing import Optional, List, Dict

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class AiOnTheEdgeSource(Source):

    def __init__(self, config):
        super().__init__(config)

        self._host = config['host']
        self._port = config.get('port', 80)
        self._value = config.get('value', 'main')

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        reply = requests.get(f'http://{self._host}:{self._port}/json', timeout=10)
        data = reply.json()
        data = data.get(self._value, {})

        values = ValueSet(labels=['type'])
        values.add(Value(self.to_float(data['value']), ['value']))
        values.add(Value(self.to_float(data['rate']), ['rate']))
        values.add(Value(self.to_float(data['pre']), ['pre']))

        has_error = data['error'] != 'no error'
        values.add(Value(1 if has_error else 0, ['error']))
        return values

    def to_float(self, val: str) -> float:
        if val == '':
            return 0
        return float(val)
