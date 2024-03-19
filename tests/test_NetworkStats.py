import ipaddress
from unittest import TestCase

from pollect.sources.helper.NetworkStats import NetworkMetricsCounter


class TestNetworkStats(TestCase):

    def test_in_network(self):
        net = NetworkMetricsCounter('', '192.168.1.0/24')
        self.assertTrue(net.contains(int(ipaddress.ip_address('192.168.1.1'))))
        self.assertTrue(net.contains(int(ipaddress.ip_address('192.168.1.10'))))
        self.assertFalse(net.contains(int(ipaddress.ip_address('192.168.2.0'))))

        net = NetworkMetricsCounter('', '0.0.0.0/0')
        self.assertTrue(net.contains(int(ipaddress.ip_address('192.168.1.1'))))
