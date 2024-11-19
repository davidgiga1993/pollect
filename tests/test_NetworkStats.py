import ipaddress
import pathlib
from unittest import TestCase
from unittest.mock import patch

from pollect.sources.helper.NetworkStats import NamedNetworks, ContainerNetworkUtils


class TestNetworkStats(TestCase):

    def test_in_network(self):
        net = NamedNetworks('', ['192.168.1.0/24'])
        self.assertTrue(net.contains(int(ipaddress.ip_address('192.168.1.1'))))
        self.assertTrue(net.contains(int(ipaddress.ip_address('192.168.1.10'))))
        self.assertFalse(net.contains(int(ipaddress.ip_address('192.168.2.0'))))

        net = NamedNetworks('', ['0.0.0.0/0'])
        self.assertTrue(net.contains(int(ipaddress.ip_address('192.168.1.1'))))

    @patch('pollect.sources.helper.NetworkStats.subprocess')
    def test_get_k8s_namespace_ips(self, subprocess):
        self._own = pathlib.Path(__file__).parent.resolve()

        def check_output(args, **kwargs):
            if args[0] == 'ctr':
                if args[4] == 'list':
                    # list container
                    return """093df0dd4e350e7d7160186ab3a50edf68f7cb6a376b84cc4965ee206ae09717
13ad2b9c213710f7f0694494843941c2ab731e8686111bce32e1bf32bcef4ab6
2fdea3910c1796a282d864d9dcb286c1a954c16c923f11a8d8e2a094fc10d1a4
309948fd90e456e7837d8f5677c76fd4e94ac82861d8d8e2df4151052e692dfe
3949859d8acd4efb5e51391eac7db92236cacc18de2ec145fcf527d3f355b213
39c198abd904ae184978d88d74184afc83caa5d3114b041eef55c0c520ae7a7b
3f82da41caca69d44531a07a71e51005cdbcf5c15b18625f32fda1c9e44fbae0
6bad36d01dfb01a116719f70f2c3562aa4372b93cc71498d9535e921fa4c5c58
6e9c47fc07da85d3e0d86505d3f090f2765e16dceeffd3e8b0d1a9efc8bf2227""".encode('utf-8')

                with open(f'{self._own}/data/containerd.json') as f:
                    return f.read().encode('utf-8')

            if len(args) == 3:
                return """cni-9df1a36f-b1c5-bb30-5596-9cb89d2ba92c (id: 3)
cni-565d2649-233b-0f48-3470-ca134bb8af0e (id: 2)
cni-6d7a0806-3c24-9460-adae-a1d4652b31c4 (id: 1)
cni-0b55048d-00de-1d0a-c4bd-ffd265423655 (id: 0)""".encode('utf-8')
            if len(args) == 8: # ip netns exec cni-.. ip add show eht0
                return """2: eth0@if6: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 8951 qdisc noqueue state UP group default qlen 1000
    link/ether 4e:f1:7e:f0:81:2e brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 172.16.95.1/32 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::4cf1:7eff:fef0:812e/64 scope link
       valid_lft forever preferred_lft forever""".encode('utf-8')

        subprocess.check_output = check_output
        namespaces = ContainerNetworkUtils().get_namespace_ips()
        self.assertEquals(1, len(namespaces))
        ips = namespaces['calico-system']
        self.assertEqual(1, len(ips))
        self.assertEquals('172.16.95.1/32', ips.pop())
