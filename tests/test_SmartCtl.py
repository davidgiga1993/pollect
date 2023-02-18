import pathlib
from unittest import TestCase
from unittest.mock import patch

from pollect.sources.SmartCtlSource import SmartCtlSource


class TestSmartCtl(TestCase):

    def setUp(self) -> None:
        self._own = pathlib.Path(__file__).parent.resolve()

    @patch('pollect.sources.SmartCtlSource.subprocess.check_output')
    @patch('pollect.sources.SmartCtlSource.os')
    def test_simple_2(self, mock_os, mock_check_output):
        mock_os.listdir.return_value = ['sda']
        with open(f'{self._own}/data/nvme.json') as f:
            mock_check_output.return_value = f.read().encode('utf-8')

        data = {'attributes': ['temperature_sensors', 'available_spare'],
                'devices': ['sda'],
                'type': '-'}
        source = SmartCtlSource(data)
        results = source.probe()[0]
        self.assertEqual(3, len(results.values))
        self.assertEqual(100, results.values[0].value)
        self.assertEqual(36, results.values[2].value)
        self.assertEqual(36, results.values[1].value)

    @patch('pollect.sources.SmartCtlSource.subprocess.check_output')
    @patch('pollect.sources.SmartCtlSource.os')
    def test_simple(self, mock_os, mock_check_output):
        mock_os.listdir.return_value = ['sda']
        with open(f'{self._own}/data/sda.json') as f:
            mock_check_output.return_value = f.read().encode('utf-8')

        data = {'attributes': ['Power_Cycle_Count'],
                'devices': ['sda'],
                'type': '-'}
        source = SmartCtlSource(data)
        results = source.probe()[0]
        self.assertEqual(1, len(results.values))
        self.assertEqual(23, results.values[0].value)

    @patch('pollect.sources.SmartCtlSource.subprocess.check_output')
    @patch('pollect.sources.SmartCtlSource.os')
    def test_regex(self, mock_os, mock_check_output):
        mock_os.listdir.return_value = ['sda', 'sda1', 'sdb', 'sdb1']
        with open(f'{self._own}/data/sda.json') as f:
            mock_check_output.return_value = f.read().encode('utf-8')

        data = {'attributes': ['Power_Cycle_Count'],
                'devices': ['sd[a-z]$'],
                'type': '-'}
        source = SmartCtlSource(data)
        results = source.probe()[0]
        self.assertEqual(2, len(results.values))
        self.assertEqual(23, results.values[0].value)
        self.assertIn('sda', results.values[0].label_values)
        self.assertEqual(23, results.values[1].value)
        self.assertIn('sdb', results.values[1].label_values)

    @patch('pollect.sources.SmartCtlSource.subprocess.check_output')
    @patch('pollect.sources.SmartCtlSource.os')
    def test_correct_unit(self, mock_os, mock_check_output):
        mock_os.listdir.return_value = ['sda']
        with open(f'{self._own}/data/sda.json') as f:
            mock_check_output.return_value = f.read().encode('utf-8')

        data = {'attributes': ['Temperature_Celsius'],
                'devices': ['sda'],
                'type': '-'}
        source = SmartCtlSource(data)
        results = source.probe()[0]
        self.assertEqual(1, len(results.values))
        self.assertEqual(32, results.values[0].value)
