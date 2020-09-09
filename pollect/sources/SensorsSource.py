import re
import subprocess

from pollect.core import Helper
from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class SensorsSource(Source):
    value_match = re.compile(r'(.+?):\s+\+?(-?[0-9.]+)')

    def __init__(self, config):
        super().__init__(config)
        self.include = Helper.remove_empty_list(config.get('include'))
        self.exclude = Helper.remove_empty_list(config.get('exclude'))

    def _probe(self):
        data = ValueSet(labels=['name'])
        lines = subprocess.check_output(['sensors']).decode('utf-8').splitlines()
        chip = None
        skip_chip = False
        for line in lines:
            line = line.lower().strip()
            if not line:
                continue

            parts = line.split(':')
            if len(parts) == 1:
                # Headline -> Chip name
                chip = line
                skip_chip = False
                if not Helper.accept(self.include, self.exclude, chip):
                    skip_chip = True
                    continue
                continue

            if parts[0] == 'adapter':
                continue

            match = self.value_match.match(line)
            if match is None:
                # End of value block
                chip = None
                continue

            if skip_chip:
                continue

            key = match.group(1).replace(' ', '_')
            value = float(match.group(2))
            data.add(Value(value, label_values=[key], name=chip))

        return data
