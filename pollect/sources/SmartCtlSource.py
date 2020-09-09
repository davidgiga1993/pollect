import os
import re
import subprocess

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class SmartCtlSource(Source):
    number_matcher = re.compile('[0-9]+')
    space_matcher = re.compile('[ \t]+')

    def __init__(self, config):
        super().__init__(config)
        self.devices = []
        self.attributes = config.get('attributes')
        devices = config.get('devices')
        items = os.listdir('/dev')
        for device in devices:
            for item in items:
                if re.match(device, item):
                    self.devices.append(item)

    def _probe(self):
        data = ValueSet(labels=['dev'])
        required_attributes = len(self.attributes)
        for dev in self.devices:
            column_count = 0
            lines = subprocess.check_output(['smartctl', '/dev/' + dev, '-a']).decode('utf-8').splitlines()

            # Ugly parsing - meh, it does the job (so far)
            found_head = False
            for line in lines:
                line = line.strip()

                if found_head:
                    columns = self.space_matcher.split(line)
                    if len(columns) < 2:
                        continue
                    attribute_name = columns[1]
                    if attribute_name not in self.attributes:
                        continue

                    # "column_count-1" is used in instead of "-1" as the actual values might contain more
                    # columns at the end which we need to ignore
                    value = self.number_matcher.search(columns[column_count - 1])
                    if not value:
                        continue
                    required_attributes -= 1
                    data.add(Value(int(value.group(0)), label_values=[dev], name=attribute_name))
                    if required_attributes == 0:
                        # We already got all the attributes - return
                        break
                    continue

                if 'ATTRIBUTE_NAME' in line:
                    found_head = True
                    column_count = len(self.space_matcher.split(line))
                    continue

        # Some attributes are missing - return all matches so far
        return data
