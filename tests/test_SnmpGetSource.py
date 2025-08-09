from time import sleep
from unittest import TestCase
from unittest.mock import patch

from pollect.core.config.ConfigContainer import ConfigContainer
from pollect.sources.SnmpGetSource import SnmpGetSource, SnmpValue


class TestSnmpGetSource(TestCase):

    def test_overflow_delta(self):
        value = SnmpValue(SnmpValue.COUNTER32, 0)
        self.assertEqual(1, value.get_delta(4294967295))

        value = SnmpValue(SnmpValue.COUNTER32, 5)
        self.assertEqual(6, value.get_delta(4294967295))

        value = SnmpValue(SnmpValue.COUNTER32, 5)
        self.assertEqual(4, value.get_delta(1))

    def test_simple(self):
        source = SnmpGetSource(ConfigContainer({
            'host': '10.1.1.1',
            'metrics': [{
                'oid': 'iso.3.6.1.2.1.16.1.1.1.3.48',
                'name': 'Test'
            }],
            'type': '-'
        }))
        # Mock _get_values to return expected SNMP values
        source._get_values = lambda oids: {
            'iso.3.6.1.2.1.16.1.1.1.3.48': SnmpValue('counter32', 123)
        }
        data = source.probe()[0]
        self.assertEqual(1, len(data.values))
        self.assertEqual(123, data.values[0].value)

    def test_simple_with_label(self):
        source = SnmpGetSource(ConfigContainer({
            'host': '10.1.1.1',
            'metrics': [{
                'oid': 'iso.3.6.1.2.1.16.1.1.1.3.48',
                'oidLabels': {
                    'paramName': 'iso.3.6.1.2.1.31.1.1.1.123'
                },
                'name': 'Test'
            }],
            'type': '-'
        }))
        source._get_values = lambda oids: {
            'iso.3.6.1.2.1.16.1.1.1.3.48': SnmpValue('counter32', 123),
            'iso.3.6.1.2.1.31.1.1.1.123': SnmpValue('string', 'sample')
        }
        data = source.probe()[0]
        self.assertEqual(1, len(data.labels))
        self.assertEqual('paramName', data.labels[0])
        self.assertEqual(1, len(data.values))
        self.assertEqual('sample', data.values[0].label_values[0])
        self.assertEqual(123, data.values[0].value)

    def test_range(self):
        config = ConfigContainer({
            'host': '10.1.1.1',
            'metrics': [{
                'oid': 'iso.3.6.1.2.1.16.1.1.1.3.${randomParam}',
                'range': {
                    'from': 1,
                    'to': 3,
                    'label': 'randomParam',
                },
                'name': 'Test'
            }],
            'type': '-'
        })
        source = SnmpGetSource(config)
        source._get_values = lambda oids: {
            'iso.3.6.1.2.1.16.1.1.1.3.1': SnmpValue('counter32', 123),
            'iso.3.6.1.2.1.16.1.1.1.3.2': SnmpValue('counter32', 10),
            'iso.3.6.1.2.1.16.1.1.1.3.3': SnmpValue('counter32', 11)
        }
        data = source.probe()[0]
        self.assertEqual(3, len(data.values))
        self.assertEqual('Test', data.values[0].name)
        self.assertEqual('Test', data.values[1].name)
        self.assertEqual('Test', data.values[2].name)
        self.assertEqual('randomParam', data.labels[0])
        self.assertEqual('1', data.values[0].label_values[0])
        self.assertEqual('2', data.values[1].label_values[0])
        self.assertEqual('3', data.values[2].label_values[0])
        self.assertEqual(123, data.values[0].value)
        self.assertEqual(10, data.values[1].value)
        self.assertEqual(11, data.values[2].value)

    def test_range_with_labels(self):
        config = ConfigContainer({
            'host': '10.1.1.1',
            'metrics': [{
                'oid': 'iso.3.6.1.2.1.16.1.1.1.3.${randomParam}',
                'oidLabels': {
                    'portName': 'iso.3.6.1.2.1.31.1.1.1.18.${randomParam}'
                },
                'range': {
                    'from': 1,
                    'to': 3,
                    'label': 'randomParam',
                },
                'name': 'Test'
            },
                {
                    'oid': 'iso.3.6.1.2.1.50.1.1.1.3.${randomParam}',
                    'oidLabels': {
                        'portName': 'iso.3.6.1.2.1.31.1.1.1.18.${randomParam}'
                    },
                    'range': {
                        'from': 1,
                        'to': 3,
                        'label': 'randomParam',
                    },
                    'name': 'Test'
                }],
            'type': '-'
        })
        source = SnmpGetSource(config)
        source._get_values = lambda oids: {
            'iso.3.6.1.2.1.16.1.1.1.3.1': SnmpValue('counter32', 123),
            'iso.3.6.1.2.1.16.1.1.1.3.2': SnmpValue('counter32', 10),
            'iso.3.6.1.2.1.16.1.1.1.3.3': SnmpValue('counter32', 11),
            'iso.3.6.1.2.1.50.1.1.1.3.1': SnmpValue('counter32', 11),
            'iso.3.6.1.2.1.31.1.1.1.18.1': SnmpValue('string', 'test name1'),
            'iso.3.6.1.2.1.31.1.1.1.18.2': SnmpValue('string', 'test name2'),
            'iso.3.6.1.2.1.31.1.1.1.18.3': SnmpValue('string', 'test name3'),
        }
        result = source.probe()
        data = result[0]
        self.assertEqual(3, len(data.values))
        self.assertEqual('Test', data.values[0].name)
        self.assertEqual('Test', data.values[1].name)
        self.assertEqual('Test', data.values[2].name)
        self.assertEqual('randomParam', data.labels[0])
        self.assertEqual('portName', data.labels[1])
        self.assertEqual('1', data.values[0].label_values[0])
        self.assertEqual('2', data.values[1].label_values[0])
        self.assertEqual('3', data.values[2].label_values[0])
        self.assertEqual('test name1', data.values[0].label_values[1])
        self.assertEqual('test name2', data.values[1].label_values[1])
        self.assertEqual('test name3', data.values[2].label_values[1])
        self.assertEqual(123, data.values[0].value)
        self.assertEqual(10, data.values[1].value)
        self.assertEqual(11, data.values[2].value)

        data = result[1]
        self.assertEqual(1, len(data.values))
        self.assertEqual('Test', data.values[0].name)
        self.assertEqual('randomParam', data.labels[0])
        self.assertEqual('portName', data.labels[1])
        self.assertEqual('1', data.values[0].label_values[0])
        self.assertEqual('test name1', data.values[0].label_values[1])
        self.assertEqual(11, data.values[0].value)

    def test_rate(self):
        source = SnmpGetSource(ConfigContainer({
            'host': '10.1.1.1',
            'metrics': [{
                'oid': 'iso.3.6.1.2.1.16.1.1.1.3.48',
                'name': 'Test',
                'mode': 'rate'
            }],
            'type': '-'
        }))
        # First run returns nothing
        source._get_values = lambda oids: {
            'iso.3.6.1.2.1.16.1.1.1.3.48': SnmpValue('counter32', 0)
        }
        data = source.probe()[0]
        self.assertEqual(0, len(data.values))
        # Wait a second
        sleep(1)
        source._get_values = lambda oids: {
            'iso.3.6.1.2.1.16.1.1.1.3.48': SnmpValue('counter32', 10)
        }
        data = source.probe()[0]
        self.assertEqual(1, len(data.values))
        # 10 units / second
        self.assertAlmostEqual(10.0, data.values[0].value, 0)

    def test_rate_overflow(self):
        source = SnmpGetSource(ConfigContainer({
            'host': '10.1.1.1',
            'metrics': [{
                'oid': 'iso.3.6.1.2.1.16.1.1.1.3.48',
                'name': 'Test',
                'mode': 'rate'
            }],
            'type': '-'
        }))
        # First run returns nothing
        source._get_values = lambda oids: {
            'iso.3.6.1.2.1.16.1.1.1.3.48': SnmpValue('counter32', 4294967290)
        }
        data = source.probe()[0]
        self.assertEqual(0, len(data.values))
        # Wait a second
        sleep(1)
        source._get_values = lambda oids: {
            'iso.3.6.1.2.1.16.1.1.1.3.48': SnmpValue('counter32', 10)
        }
        data = source.probe()[0]
        self.assertEqual(1, len(data.values))
        # 16 units / second (overflow)
        self.assertAlmostEqual(16.0, data.values[0].value, 0)
