import os
from unittest import TestCase

from pollect.sources.helper.ConfigContainer import ConfigContainer


class TestConfigContainer(TestCase):

    def test_resolve(self):
        c = ConfigContainer({
            'key': '${VALUE}',
            'key2': 'someValue${VALUE}',
            'key3': {
                'test': 'test'
            },
            'key4': [
                {'test': 'test'}
            ]
        })
        os.environ['VALUE'] = 'hello'

        self.assertEqual('hello', c.get('key'))
        self.assertEqual('hello', c['key'])
        self.assertEqual('someValuehello', c.get('key2'))
        self.assertTrue(isinstance(c.get('key3'), ConfigContainer))
        self.assertTrue(isinstance(c.get('key4')[0], ConfigContainer))

    def test_missing(self):
        c = ConfigContainer({
            'key': '${VALUE_UNUSED}',
            'key2': 'someValue${VALUE}',
        })

        try:
            c.get('key')
            self.fail('No exception raised')
        except KeyError:
            return
