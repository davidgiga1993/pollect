from unittest import TestCase

import requests

from pollect.core.ValueSet import ValueSet, Value

from pollect.writers.PrometheusWriter import PrometheusWriter
from pollect.writers.Writer import Writer


class TestPrometheusWriter(TestCase):
    writer: Writer = None

    @classmethod
    def setUpClass(cls) -> None:
        # Singleton
        if TestPrometheusWriter.writer is None:
            TestPrometheusWriter.writer = PrometheusWriter({'port': 9123})
            TestPrometheusWriter.writer.start()

    @classmethod
    def tearDownClass(cls) -> None:
        TestPrometheusWriter.writer.stop()
    def test_removal(self):
        value_set = ValueSet()
        value_set.values.append(Value(0, name='test'))
        self.writer.write([value_set])

        reply = requests.get('http://localhost:9123')
        self.assertIn('test 0.0', reply.text)

        self.writer.write([])
        reply = requests.get('http://localhost:9123')
        self.assertNotIn('test 0.0', reply.text)

        # And add again
        self.writer.write([value_set])
        reply = requests.get('http://localhost:9123')
        self.assertIn('test 0.0', reply.text)

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
