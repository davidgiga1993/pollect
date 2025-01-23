import requests
from typing import Optional, List, Dict

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class AiOnTheEdgeSource(Source):

    def __init__(self, config):
        super().__init__(config)

        self._hostname = config['host']
        self._port = config.get('port', 80)

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        reply = requests.get(f'{self._host}:{self._port}/json', timeout=10)
        data = reply.json()

        values = ValueSet(labels=['type'])
        values.add(Value(data['raw'], ['raw']))
        values.add(Value(data['value'], ['value']))
        values.add(Value(data['rate'], ['rate']))

        has_error = data['error'] != 'no error'
        values.add(Value(1 if has_error else 0, ['error'])
        return values
