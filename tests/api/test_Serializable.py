from unittest import TestCase

from pollect.libs.api.Serializable import Serializable


class A(Serializable):
    def __init__(self):
        super().__init__()
        self.a = 1
        self.b = None
        self.child = B()
        self.children = [B(), B()]


class B(Serializable):
    def __init__(self):
        super().__init__()
        self.a = 'from b'


class TestSerializable(TestCase):

    def test_to_dict(self):
        data = A().get_data()
        self.assertEqual({'a': 1, 'b': None,
                          'child': {'a': 'from b'},
                          'children': [{'a': 'from b'}, {'a': 'from b'}],
                          }, data)
