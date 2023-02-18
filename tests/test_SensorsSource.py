from unittest import TestCase
from unittest.mock import patch

from pollect.sources.SensorsSource import SensorsSource


class TestSensorsSource(TestCase):
    OUT = '''
nct6798-isa-0290
Adapter: ISA adapter
in0:                   360.00 mV (min =  +0.00 V, max =  +1.74 V)
in1:                     1.67 V  (min =  +0.00 V, max =  +0.00 V)  ALARM
in2:                     3.44 V  (min =  +0.00 V, max =  +0.00 V)  ALARM
in3:                     3.36 V  (min =  +0.00 V, max =  +0.00 V)  ALARM
in4:                     1.86 V  (min =  +0.00 V, max =  +0.00 V)  ALARM
in5:                   856.00 mV (min =  +0.00 V, max =  +0.00 V)  ALARM
in6:                     1.21 V  (min =  +0.00 V, max =  +0.00 V)  ALARM
in7:                     3.44 V  (min =  +0.00 V, max =  +0.00 V)  ALARM
in8:                     3.26 V  (min =  +0.00 V, max =  +0.00 V)  ALARM
in9:                   912.00 mV (min =  +0.00 V, max =  +0.00 V)  ALARM
in10:                    1.02 V  (min =  +0.00 V, max =  +0.00 V)  ALARM
in11:                  632.00 mV (min =  +0.00 V, max =  +0.00 V)  ALARM
in12:                    1.05 V  (min =  +0.00 V, max =  +0.00 V)  ALARM
in13:                  920.00 mV (min =  +0.00 V, max =  +0.00 V)  ALARM
in14:                  904.00 mV (min =  +0.00 V, max =  +0.00 V)  ALARM
fan1:                     0 RPM  (min =    0 RPM)
fan2:                  1869 RPM  (min =    0 RPM)
fan3:                  1648 RPM  (min =    0 RPM)
fan4:                     0 RPM  (min =    0 RPM)
fan5:                  1542 RPM  (min =    0 RPM)
fan6:                     0 RPM  (min =    0 RPM)
fan7:                     0 RPM  (min =    0 RPM)
SYSTIN:                 +35.0°C  (high = +80.0°C, hyst = +75.0°C)  sensor = thermistor
CPUTIN:                 +29.0°C  (high = +80.0°C, hyst = +75.0°C)  sensor = thermistor
AUXTIN0:                +15.5°C    sensor = thermistor
AUXTIN1:                -62.0°C    sensor = thermistor
AUXTIN2:                +12.0°C    sensor = thermistor
AUXTIN3:                +31.0°C    sensor = thermistor
SMBUSMASTER 0:          +31.0°C
PCH_CHIP_CPU_MAX_TEMP:   +0.0°C
PCH_CHIP_TEMP:           +0.0°C
PCH_CPU_TEMP:            +0.0°C
intrusion0:            ALARM
intrusion1:            ALARM
beep_enable:           disabled

amdgpu-pci-0700
Adapter: PCI adapter
vddgfx:        1.16 V
vddnb:       931.00 mV
edge:         +28.0°C
slowPPT:       2.00 mW

nvme-pci-0400
Adapter: PCI adapter
Composite:    +35.9°C  (low  = -273.1°C, high = +80.8°C)
                       (crit = +84.8°C)
Sensor 1:     +35.9°C  (low  = -273.1°C, high = +65261.8°C)
Sensor 2:     +35.9°C  (low  = -273.1°C, high = +65261.8°C)

k10temp-pci-00c3
Adapter: PCI adapter
Tctl:         +31.0°C

nvme-pci-0600
Adapter: PCI adapter
Composite:    +37.9°C  (low  = -273.1°C, high = +80.8°C)
                       (crit = +84.8°C)
Sensor 1:     +37.9°C  (low  = -273.1°C, high = +65261.8°C)
Sensor 2:     +36.9°C  (low  = -273.1°C, high = +65261.8°C)

'''

    @patch('pollect.sources.SensorsSource.subprocess.check_output')
    def test_simple(self, mock_check_output):
        mock_check_output.return_value = self.OUT.encode('utf-8')
        source = SensorsSource({'type': '-'})
        results = source.probe()[0]

        self.assertEqual('nct6798-isa-0290', results.values[0].label_values[0])
        self.assertEqual('in0', results.values[0].label_values[1])
        self.assertEqual('V', results.values[0].label_values[2])
        self.assertEqual(0.360, results.values[0].value)

        self.assertEqual('nct6798-isa-0290', results.values[16].label_values[0])
        self.assertEqual('fan2', results.values[16].label_values[1])
        self.assertEqual('RPM', results.values[16].label_values[2])
        self.assertEqual(1869, results.values[16].value)

        self.assertEqual('amdgpu-pci-0700', results.values[32].label_values[0])
        self.assertEqual('vddgfx', results.values[32].label_values[1])
        self.assertEqual('V', results.values[32].label_values[2])
        self.assertEqual(1.16, results.values[32].value)

        self.assertEqual('nvme-pci-0400', results.values[36].label_values[0])
        self.assertEqual('composite', results.values[36].label_values[1])
        self.assertEqual('°C', results.values[36].label_values[2])

        self.assertEqual('nvme-pci-0400', results.values[37].label_values[0])
        self.assertEqual('sensor_1', results.values[37].label_values[1])
        self.assertEqual('°C', results.values[37].label_values[2])

