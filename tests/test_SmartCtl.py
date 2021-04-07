from unittest import TestCase
from unittest.mock import patch

from pollect.sources.SmartCtlSource import SmartCtlSource


class TestSmartCtl(TestCase):
    OUT = b'''
SMART Attributes Data Structure revision number: 10
Vendor Specific SMART Attributes with Thresholds:
ID# ATTRIBUTE_NAME          FLAG     VALUE WORST THRESH TYPE      UPDATED  WHEN_FAILED RAW_VALUE
  1 Raw_Read_Error_Rate     0x000f   111   099   006    Pre-fail  Always       -       37180691
  3 Spin_Up_Time            0x0003   095   095   000    Pre-fail  Always       -       0
  4 Start_Stop_Count        0x0032   100   100   020    Old_age   Always       -       98
  5 Reallocated_Sector_Ct   0x0033   047   047   036    Pre-fail  Always       -       2203
  7 Seek_Error_Rate         0x000f   078   060   030    Pre-fail  Always       -       61542769
  9 Power_On_Hours          0x0032   035   035   000    Old_age   Always       -       57479
 10 Spin_Retry_Count        0x0013   100   100   097    Pre-fail  Always       -       0
 12 Power_Cycle_Count       0x0032   100   100   020    Old_age   Always       -       98
183 Runtime_Bad_Block       0x0032   100   100   000    Old_age   Always       -       0
184 End-to-End_Error        0x0032   100   100   099    Old_age   Always       -       0
187 Reported_Uncorrect      0x0032   100   100   000    Old_age   Always       -       0
188 Command_Timeout         0x0032   100   099   000    Old_age   Always       -       2
189 High_Fly_Writes         0x003a   100   100   000    Old_age   Always       -       0
190 Airflow_Temperature_Cel 0x0022   068   051   045    Old_age   Always       -       32 (Min/Max 27/40)
194 Temperature_Celsius     0x0022   032   049   000    Old_age   Always       -       32 (0 12 0 0 0)
195 Hardware_ECC_Recovered  0x001a   029   017   000    Old_age   Always       -       37180691
197 Current_Pending_Sector  0x0012   100   100   000    Old_age   Always       -       0
198 Offline_Uncorrectable   0x0010   100   100   000    Old_age   Offline      -       0
199 UDMA_CRC_Error_Count    0x003e   200   200   000    Old_age   Always       -       0
240 Head_Flying_Hours       0x0000   100   253   000    Old_age   Offline      -       57743 (128 97 0)
241 Total_LBAs_Written      0x0000   100   253   000    Old_age   Offline      -       361734619
242 Total_LBAs_Read         0x0000   100   253   000    Old_age   Offline      -       142518040
    '''

    @patch('pollect.sources.SmartCtlSource.subprocess.check_output')
    @patch('pollect.sources.SmartCtlSource.os')
    def test_simple(self, mock_os, mock_check_output):
        mock_os.listdir.return_value = ['sda']
        mock_check_output.return_value = self.OUT
        data = {'attributes': ['Power_Cycle_Count'],
                'devices': ['sda'],
                'type': '-'}
        source = SmartCtlSource(data)
        results = source.probe()[0]
        self.assertEqual(1, len(results.values))
        self.assertEqual(98, results.values[0].value)

    @patch('pollect.sources.SmartCtlSource.subprocess.check_output')
    @patch('pollect.sources.SmartCtlSource.os')
    def test_regex(self, mock_os, mock_check_output):
        mock_os.listdir.return_value = ['sda', 'sda1', 'sdb', 'sdb1']
        mock_check_output.return_value = self.OUT
        data = {'attributes': ['Power_Cycle_Count'],
                'devices': ['sd[a-z]$'],
                'type': '-'}
        source = SmartCtlSource(data)
        results = source.probe()[0]
        self.assertEqual(2, len(results.values))
        self.assertEqual(98, results.values[0].value)
        self.assertIn('sda', results.values[0].label_values)
        self.assertEqual(98, results.values[1].value)
        self.assertIn('sdb', results.values[1].label_values)

    @patch('pollect.sources.SmartCtlSource.subprocess.check_output')
    @patch('pollect.sources.SmartCtlSource.os')
    def test_start_padding(self, mock_os, mock_check_output):
        mock_os.listdir.return_value = ['sda']
        mock_check_output.return_value = self.OUT
        data = {'attributes': ['Raw_Read_Error_Rate'],
                'devices': ['sda'],
                'type': '-'}
        source = SmartCtlSource(data)
        results = source.probe()[0]
        self.assertEqual(1, len(results.values))
        self.assertEqual(37180691, results.values[0].value)

    @patch('pollect.sources.SmartCtlSource.subprocess.check_output')
    @patch('pollect.sources.SmartCtlSource.os')
    def test_complex_extract(self, mock_os, mock_check_output):
        mock_os.listdir.return_value = ['sda']
        mock_check_output.return_value = self.OUT
        data = {'attributes': ['Airflow_Temperature_Cel'],
                'devices': ['sda'],
                'type': '-'}
        source = SmartCtlSource(data)
        results = source.probe()[0]
        self.assertEqual(32, results.values[0].value)
