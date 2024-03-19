import datetime
import ipaddress
import json
import re
import subprocess
from typing import Dict, List


class NetworkMetrics:
    bytes_to_network: int
    bytes_from_network: int

    def __init__(self, bytes_to_network: int = 0, bytes_from_network: int = 0):
        self.bytes_to_network = bytes_to_network
        self.bytes_from_network = bytes_from_network

    def divide(self, delta):
        self.bytes_to_network = self.bytes_to_network / delta
        self.bytes_from_network = self.bytes_from_network / delta


class Subnet:
    def __init__(self, subnet: str):
        subnet: ipaddress.IPv4Network = ipaddress.ip_network(subnet)
        self._netw: int = int(subnet.network_address)
        self._mask: int = int(subnet.netmask)

    def contains(self, ip: int):
        return (ip & self._mask) == self._netw


class NetworkMetricsCounter:
    """
    Holds the count of bytes per IP subnet
    """

    def __init__(self, name: str, subnets: List[str]):
        self.name = name
        self._subnets: List[Subnet] = []
        for subnet in subnets:
            self._subnets.append(Subnet(subnet))

        self.bytes_to_network: int = 0
        self.bytes_from_network: int = 0
        self.last_reset: datetime.datetime = datetime.datetime.now()

    def contains(self, ip: int):
        for net in self._subnets:
            if net.contains(ip):
                return True
        return False

    def get_per_second(self, now: datetime.datetime) -> NetworkMetrics:
        delta = (now - self.last_reset).total_seconds()
        self.last_reset = now

        metrics = NetworkMetrics(self.bytes_to_network, self.bytes_from_network)
        metrics.divide(delta)

        self.bytes_to_network = 0
        self.bytes_from_network = 0
        return metrics


class ContainerNetworkUtils:

    @staticmethod
    def get_namespace_ips():
        """
        Returns a list of all k8s container IP addresses on the current node grouped by namespace.
        This requires containerd as runtime.
        """
        namespace_ips_map = {}

        nic_ns = ContainerNetworkUtils.get_container_ips()
        lines = subprocess.check_output(['ctr', '-n', 'k8s.io', 'containers', 'list', '-q']) \
            .decode('utf-8').splitlines()

        for container_id in lines:
            # Find the network namespace of the container
            json_str = subprocess.check_output(['ctr', '-n', 'k8s.io', 'container', 'info', container_id]) \
                .decode('utf-8')
            data = json.loads(json_str)
            k8s_namespace = data.get('Labels', {}).get('io.kubernetes.pod.namespace', '')
            network_namespace = None
            for linux_ns in data.get('Spec', {}).get('linux', {}).get('namespaces', []):
                if linux_ns.get('type') == 'network':
                    # Get last argument of path
                    network_namespace = linux_ns['path'].split('/')[-1]
                    break
            if network_namespace is None:
                # No network namespace found
                continue

            container_ip = nic_ns.get(network_namespace)
            if container_ip is None:
                # No IP found, maybe the container was created just in this moment?
                continue
            if k8s_namespace not in namespace_ips_map:
                namespace_ips_map[k8s_namespace] = set()
            namespace_ips_map[k8s_namespace].add(container_ip)
        return namespace_ips_map

    @staticmethod
    def get_container_ips() -> Dict[str, str]:
        """
        Returns a list of all k8s container IP addresses on the current node.
        :return: Dict of networks in the CIDR notation mapped to their network namespace
        """
        networks = {}
        lines = subprocess.check_output(['ip', 'netns', 'list']).decode('utf-8').splitlines()
        for line in lines:
            namespace_name = line.split(' ', 2)[0]
            ips = subprocess.check_output(['ip', 'netns', 'exec', namespace_name, 'ip', 'addr', 'show', 'eth0']) \
                .decode('utf-8')

            matches = re.findall(r'inet (.+?) ', ips)
            if len(matches) > 0:
                networks[namespace_name] = matches[0]
        return networks
