from unittest import TestCase

import requests

from pollect.core.ValueSet import ValueSet, Value

from pollect.writers.PrometheusWriter import PrometheusWriter


class TestPrometheusWriter(TestCase):
    writer: PrometheusWriter = None

    @classmethod
    def setUpClass(cls) -> None:
        # Singleton
        if TestPrometheusWriter.writer is None:
            TestPrometheusWriter.writer = PrometheusWriter({'port': 9123})
            TestPrometheusWriter.writer.start()

    @classmethod
    def tearDownClass(cls) -> None:
        TestPrometheusWriter.writer.stop()

    def setUp(self) -> None:
        self.writer.clear()

    def test_removal_labels(self):
        value_set = ValueSet(labels=['a'])
        value_set.values.append(Value(0, name='test', label_values=['1']))
        value_set.values.append(Value(0, name='test', label_values=['2']))
        self.writer.write([value_set])

        reply = requests.get('http://localhost:9123')
        self.assertIn('test{a="1"} 0.0', reply.text)
        self.assertIn('test{a="2"} 0.0', reply.text)

        self.writer.write([])
        reply = requests.get('http://localhost:9123')
        self.assertNotIn('test{a="1"} 0.0', reply.text)
        self.assertNotIn('test{a="2"} 0.0', reply.text)
        self.assertEqual(1, len(self.writer._cache._prom_counter))
        self.assertEqual(1, len(self.writer._cache._source_metrics))

        # And add again
        self.writer.write([value_set])
        reply = requests.get('http://localhost:9123')
        self.assertIn('test{a="1"} 0.0', reply.text)
        self.assertIn('test{a="2"} 0.0', reply.text)

        # Only write one
        value_set.values.pop()
        self.writer.write([value_set])
        reply = requests.get('http://localhost:9123')
        self.assertIn('test{a="1"} 0.0', reply.text)
        self.assertNotIn('test{a="2"} 0.0', reply.text)
        self.assertEqual(1, len(self.writer._cache._prom_counter))
        self.assertEqual(1, len(self.writer._cache._source_metrics))

    def test_multi_label_partial_write(self):
        value_set_a = ValueSet(labels=['a'])
        value_set_a.values.append(Value(0, name='test', label_values=['2']))

        value_set_b = ValueSet(labels=['a'])
        value_set_b.values.append(Value(0, name='test', label_values=['1']))
        value_set_b.values.append(Value(0, name='test2', label_values=['1']))
        self.writer.write([value_set_a], value_set_a)
        self.writer.write([value_set_b], value_set_b)

        reply = requests.get('http://localhost:9123')
        self.assertIn('test{a="1"} 0.0', reply.text)
        self.assertIn('test2{a="1"} 0.0', reply.text)
        self.assertIn('test{a="2"} 0.0', reply.text)

        self.writer.write([], value_set_a)
        reply = requests.get('http://localhost:9123')
        self.assertIn('test{a="1"} 0.0', reply.text)
        self.assertNotIn('test{a="2"} 0.0', reply.text)

        # And add again
        self.writer.write([value_set_a], value_set_a)
        self.writer.write([value_set_b], value_set_b)
        reply = requests.get('http://localhost:9123')
        self.assertIn('test{a="1"} 0.0', reply.text)
        self.assertIn('test{a="2"} 0.0', reply.text)

        # Remove value set b
        self.writer.write([], value_set_b)
        reply = requests.get('http://localhost:9123')
        self.assertNotIn('test{a="1"} 0.0', reply.text)
        self.assertNotIn('test2{a="1"} 0.0', reply.text)
        self.assertIn('test{a="2"} 0.0', reply.text)

        # Add B again
        self.writer.write([value_set_b], value_set_b)
        # Remove single value from B
        value_set_b.values.pop()
        self.writer.write([value_set_b], value_set_b)
        reply = requests.get('http://localhost:9123')
        self.assertIn('test{a="1"} 0.0', reply.text)
        self.assertNotIn('test2{a="1"} 0.0', reply.text)

    def test_removal_partial_write(self):
        value_set = ValueSet()
        value_set.values.append(Value(0, name='test1'))
        self.writer.write([value_set], 1)

        value_set = ValueSet()
        value_set.values.append(Value(0, name='test2'))
        self.writer.write([value_set], 2)

        reply = requests.get('http://localhost:9123')
        self.assertIn('test1 0.0', reply.text)
        self.assertIn('test2 0.0', reply.text)

        self.writer.write([], 1)
        reply = requests.get('http://localhost:9123')
        self.assertNotIn('test1 0.0', reply.text)
        self.assertIn('test2 0.0', reply.text)
