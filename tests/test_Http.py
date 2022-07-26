from unittest import TestCase
from unittest.mock import patch

from pollect.sources.HttpSource import HttpSource

from pollect.sources.SmartCtlSource import SmartCtlSource


class TestHttp(TestCase):

    def test_single(self):
        data = {'url': 'https://github.com', 'type': ''}
        source = HttpSource(data)
        results = source.probe()[0]
        self.assertEqual(1, len(results.values))
        self.assertEqual(0, len(results.labels))
        self.assertEqual(0, len(results.values[0].label_values))
        self.assertTrue(results.values[0].value < 15000)

    def test_multi(self):
        data = {'url': ['https://github.com',
                        'https://github.com/davidgiga1993'], 'type': ''}
        source = HttpSource(data)
        results = source.probe()[0]
        self.assertEqual(1, len(results.labels))
        self.assertEqual('url', results.labels[0])
        self.assertEqual(2, len(results.values))
        self.assertEqual(1, len(results.values[0].label_values))
        self.assertEqual('https://github.com', results.values[0].label_values[0])
