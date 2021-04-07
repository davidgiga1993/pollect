from unittest import TestCase
from unittest.mock import patch

from pollect.sources.SensorsSource import SensorsSource


class TestSensorsSource(TestCase):
    OUT = '''
    asus-isa-0000
Adapter: ISA adapter
cpu_fan:        0 RPM

acpitz-virtual-0
Adapter: Virtual device
temp1:        +27.8°C  (crit = +119.0°C)
temp2:        +29.8°C  (crit = +119.0°C)

coretemp-isa-0000
Adapter: ISA adapter
Physical id 0:  +30.0°C  (high = +80.0°C, crit = +100.0°C)
Core 0:         +29.0°C  (high = +80.0°C, crit = +100.0°C)
Core 1:         +30.0°C  (high = +80.0°C, crit = +100.0°C)
'''

    @patch('pollect.sources.SensorsSource.subprocess.check_output')
    def test_simple(self, mock_check_output):
        mock_check_output.return_value = self.OUT.encode('utf-8')
        source = SensorsSource({'type': '-'})
        results = source.probe()[0]

        self.assertEqual('asus-isa-0000', results.values[0].name)
        self.assertEqual('cpu_fan', results.values[0].label_values[0])

        self.assertEqual('acpitz-virtual-0', results.values[1].name)
        self.assertEqual('temp1', results.values[1].label_values[0])

        self.assertEqual('coretemp-isa-0000', results.values[3].name)
        self.assertEqual('physical_id_0', results.values[3].label_values[0])

        self.assertEqual(0, results.values[0].value)
        self.assertEqual(27.8, results.values[1].value)
        self.assertEqual(29.8, results.values[2].value)
        self.assertEqual(30, results.values[3].value)
        self.assertEqual(29, results.values[4].value)
        self.assertEqual(30, results.values[5].value)
