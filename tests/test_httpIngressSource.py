from unittest import TestCase
from unittest.mock import patch

import requests

from pollect.sources.HttpIngressSource import HttpIngressSource
from pollect.sources.HttpSource import HttpSource

from pollect.sources.SmartCtlSource import SmartCtlSource


class TestHttpIngressSource(TestCase):

    def tearDown(self) -> None:
        if self.source is not None:
            self.source.shutdown()

    def test_counter(self):
        data = {
            'type': '',
            'port': 9006,
            'metrics': {
                'sample_metric': {
                    'type': 'counter',
                    'labels': ['host']
                }
            }
        }

        self.source = HttpIngressSource(data)
        self.source.setup({})
        results = self.source.probe()
        self.assertEqual(1, len(results))
        self.assertEqual(0, len(results[0].values))

        r = requests.post('http://localhost:9006', json={'metrics': {
            'sample_metric': {
                'value': 1,
                'labels': {
                    'host': 'a'
                }
            }
        }})
        self.assertEqual(200, r.status_code)
        results = self.source.probe()

        self.assertEqual(1, len(results))
        self.assertEqual(1, len(results[0].values))
        self.assertEqual(1, results[0].values[0].value)

        r = requests.post('http://localhost:9006', json={'metrics': {
            'sample_metric': {
                'value': 2,
                'labels': {
                    'host': 'a'
                }
            }
        }})
        self.assertEqual(200, r.status_code)
        results = self.source.probe()
        self.assertEqual(1, len(results[0].values))
        self.assertEqual(3, results[0].values[0].value)

    def test_gauge(self):
        data = {
            'type': '',
            'port': 9006,
            'metrics': {
                'sample_metric': {
                    'labels': ['host']
                }
            }
        }

        self.source = HttpIngressSource(data)
        self.source.setup({})
        results = self.source.probe()
        self.assertEqual(1, len(results))
        self.assertEqual(0, len(results[0].values))

        r = requests.post('http://localhost:9006', json={'metrics': {
            'sample_metric': {
                'value': 1,
                'labels': {
                    'host': 'a'
                }
            }
        }})
        self.assertEqual(200, r.status_code)
        results = self.source.probe()

        self.assertEqual(1, len(results))
        self.assertEqual(1, len(results[0].values))
        self.assertEqual(1, results[0].values[0].value)

        r = requests.post('http://localhost:9006', json={'metrics': {
            'sample_metric': {
                'value': 2,
                'labels': {
                    'host': 'a'
                }
            }
        }})
        self.assertEqual(200, r.status_code)
        results = self.source.probe()
        self.assertEqual(1, len(results[0].values))
        self.assertEqual(2, results[0].values[0].value)
