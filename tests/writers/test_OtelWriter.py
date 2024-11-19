from unittest import TestCase


from pollect.core.ValueSet import ValueSet
from pollect.writers.OtelWriter import OtelWriter


class TestOtelWriter(TestCase):
    writer: OtelWriter = None

    @classmethod
    def setUpClass(cls) -> None:
        # Singleton
        if TestOtelWriter.writer is None:
            TestOtelWriter.writer = OtelWriter({})
            TestOtelWriter.writer.start()

    @classmethod
    def tearDownClass(cls) -> None:
        TestOtelWriter.writer.stop()

    def test_get_attributes_from_labels(self):
        labels = ['a', 'b']
        label_values = ['1', '2']
        attributes = TestOtelWriter.writer._get_attributes_from_labels(labels, label_values)
       
        assert attributes == {'a': '1', 'b': '2'}

    def test_get_or_create_gauge(self):
        # Execute twice to test if on first call the gauge is created and on the second the existing gauge is returned
        gauge = TestOtelWriter.writer._get_or_create_gauge('test')
        gauge = TestOtelWriter.writer._get_or_create_gauge('test')
        assert self.writer._gauges['test'] == gauge
