from unittest import TestCase

from pollect.sources.CertificateSource import CertificateSource


class TestCertificate(TestCase):

    def test_single(self):
        data = {'url': 'https://postman-echo.com/status/200', 'type': ''}
        source = CertificateSource(data)
        results = source.probe()[0]
        self.assertEqual(1, len(results.values))
        self.assertEqual(0, len(results.labels))
        self.assertTrue(results.values[0].value > 10)
