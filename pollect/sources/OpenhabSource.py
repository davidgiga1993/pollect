import re
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
        reply = requests.get(self._url + '/rest/items')
        data = reply.json()

        value_set = ValueSet(labels=['name', 'group'])
        for item in data:
            item_type = item.get('type')
            group_names = ','.join(item.get('groupNames', []))
            label = item.get('label')
            if label is None:
                continue

            # Sanitize label name
            label = re.sub(r'[^a-zA-Z0-9_:]+', '_', label)

            state = item.get('state')
            if item_type.startswith('Number'):
                # Number might be formatted, try a simple split by space
                # to get the number without unit
                state = state.split(' ')[0]
                try:
                    number = float(state)
                    value_set.add(Value(number, label_values=[item['name'], group_names], name=label))
                except ValueError:
                    # Value might be null
                    continue
            if item_type == 'Switch':
                value_set.add(Value(state == 'ON', label_values=[item['name'], group_names], name=label))

        return value_set
