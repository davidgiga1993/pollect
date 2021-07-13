from typing import Optional, List

import requests

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class OpenhabSource(Source):
    """
    Collects all channels of all items in openhab and exports them (if numeric value)
    """

    def __init__(self, config):
        super().__init__(config)
        self._url = config.get('url')

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        reply = requests.get(self._url + '/rest/items?recursive=true')
        data = reply.json()

        value_set = ValueSet(labels=['group'])
        for item in data:
            item_type = item.get('type')
            group_names = ','.join(item.get('groupNames', []))
            state = item.get('state')

            if item_type == 'Number':
                try:
                    number = float(state)
                    value_set.add(Value(number, label_values=[group_names], name=item['name']))
                except ValueError:
                    # Value might be null
                    continue
            if item_type == 'Switch':
                value_set.add(Value(state == 'ON', label_values=[group_names], name=item['name']))

        return value_set
