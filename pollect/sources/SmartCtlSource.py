import json
import os
import re
import subprocess

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class SmartCtlSource(Source):
    def __init__(self, config):
        super().__init__(config)
        self.devices = []
        self.attributes = set(config.get('attributes'))
        devices = config.get('devices')
        items = os.listdir('/dev')
        for device in devices:
            for item in items:
                if re.match(device, item):
                    self.devices.append(item)

    def _probe(self):
        values = ValueSet(labels=['attribute', 'dev'])
        for dev in self.devices:
            json_str = subprocess.check_output(['smartctl', '--json', '/dev/' + dev, '-a']).decode('utf-8')
            data = json.loads(json_str)

            attributes_data = data.get('ata_smart_attributes')
            if attributes_data:
                for attr_data in attributes_data['table']:
                    attr_name = attr_data['name']
                    # Use string since it's already converted into the correct format
                    value = attr_data.get('raw', {}).get('string')
                    if value:
                        # Convert the string into a regular number
                        value = int(value.split(' ')[0].strip())
                    else:
                        # Fallback to normalized value
                        value = attr_data['value']

                    if self._include_attribute(attr_name):
                        values.add(Value(int(value), label_values=[attr_name, dev]))

            # NVME format?
            nvme_health = data.get('nvme_smart_health_information_log')
            if nvme_health:
                for attr_name, value in nvme_health.items():
                    if self._include_attribute(attr_name):
                        if isinstance(value, list):
                            for idx in range(len(value)):
                                values.add(Value(int(value[idx]),
                                                 label_values=[attr_name + '_' + str(idx), dev]))
                            continue

                        values.add(Value(int(value), label_values=[attr_name, dev]))

        # Some attributes are missing - return all matches so far
        return values

    def _include_attribute(self, attr_name: str) -> bool:
        return len(self.attributes) == 0 or attr_name in self.attributes
