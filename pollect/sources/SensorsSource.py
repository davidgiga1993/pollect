import re
import subprocess
from typing import Tuple

from pollect.core import Helper
from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class SensorsSource(Source):
    value_match = re.compile(r'(.+?):\s+\+?(-?[0-9.]+)(.*)')

    def __init__(self, config):
        super().__init__(config)
        self._use_base_units = config.get('useBaseUnits', True)
        self.include = Helper.remove_empty_list(config.get('include'))
        self.exclude = Helper.remove_empty_list(config.get('exclude'))

    def _probe(self):
        data = ValueSet(labels=['device', 'name', 'unit'])
        lines = subprocess.check_output(['sensors']).decode('utf-8').splitlines()
        device = None
        skip_chip = False
        for line in lines:
            if line.startswith(' '):
                # Line continuation from previous sensor
                continue

            line = line.strip()
            if not line:
                continue

            parts = line.split(':')
            if len(parts) == 1:
                # New device
                device = line.lower()
                skip_chip = False
                if not Helper.accept(self.include, self.exclude, device):
                    skip_chip = True
                    continue
                continue

            if parts[0] == 'Adapter':
                continue

            match = self.value_match.match(line)
            if match is None:
                # End of block
                device = None
                continue

            if skip_chip:
                continue

            key = match.group(1).replace(' ', '_').lower()
            value = float(match.group(2))
            value, unit = self._to_unit(value, match.group(3))

            data.add(Value(value, label_values=[device, key, unit]))

        return data

    def _to_unit(self, value: float, suffix: str) -> Tuple[float, str]:
        """
        Converts the given suffix of a sensors to the value unit.
        Example:  " mV (min = ...)" -> "mV".
        Depending on the probe configuration, the base unit is returned instead

        :param value: Raw value
        :param suffix: Suffix of the sensor data
        :return: New (normalized) value and unit
        """
        parts = suffix.strip().split(' ')
        unit = parts[0]
        if not self._use_base_units:
            return value, unit
        if unit.startswith('°'):
            return value, unit

        if len(unit) == 2:
            unit_factors = ['m', '', 'k', 'M', 'G']
            factor = 0.001
            for unit_segment in unit_factors:
                if unit_segment == unit[0]:
                    return value * factor, unit[1]
                # The unit doesn't match
                factor = factor * 1000

        # Nothing to convert
        return value, unit
