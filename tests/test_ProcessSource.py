from unittest import TestCase

from pollect.sources.ProcessSource import ProcessSource


class TestProcessSource(TestCase):
    def test_simple_query(self):
        source = ProcessSource({
            'name': 'test',
            'procRegex': 'python.+',
            'type': '-'
        })
        data = source.probe()[0]
        self.assertIsNotNone(data)
        self.assertGreater(data.values[-1].value, 0)
        self.assertIsNotNone(data.values[0])
        self.assertIsNotNone(data.values[1])
