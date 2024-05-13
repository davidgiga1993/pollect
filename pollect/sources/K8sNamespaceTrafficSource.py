from __future__ import annotations

import ipaddress
import os
from typing import Optional, List, NamedTuple, Dict, Callable

from bcc import BPF

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source
from pollect.sources.helper.NetworkStats import NamedNetworks, ContainerNetworkUtils, NetworkMetrics


class K8sNamespaceTrafficSource(Source):
    """
    Collects network traffic statistics using eBPF.
    """

    _b: BPF

    def __init__(self, config):
        super().__init__(config)
        self._namespace_label = config.get('namespaceLabel', 'namespace')
        self._traffic_log_mode = config.get('trafficLog')

        self.known_networks: List[NamedNetworks] = []
        for network in config.get('networks', []):
            name = network['name']
            self.known_networks.append(NamedNetworks(name, network['cidrs']))

        # Add catch-any as last item
        self.known_networks.append(NamedNetworks('other', ['0.0.0.0/0'], catch_all=True))
        self._metrics = NamespacesMetrics(self.known_networks)

    def setup_source(self, global_conf):
        src_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bpf', 'tcp.c')
        b = BPF(src_file=src_file)
        b.attach_kprobe(event='tcp_sendmsg', fn_name='tcp_send_entry')
        b.attach_kprobe(event='tcp_cleanup_rbuf', fn_name='tcp_cleanup_rbuf')
        b.attach_kretprobe(event='tcp_sendmsg', fn_name='tcp_send_ret')
        if BPF.get_kprobe_functions(b'tcp_sendpage'):
            b.attach_kprobe(event='tcp_sendpage', fn_name='tcp_send_entry')
            b.attach_kretprobe(event='tcp_sendpage', fn_name='tcp_send_ret')
        self._b = b

        if self._traffic_log_mode is not None:
            self.log.info(f'Traffic logging enabled: {self._traffic_log_mode}')

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        self._metrics.update_networks()

        ipv4_send_bytes = self._b["ipv4_send_bytes"]
        ipv4_recv_bytes = self._b["ipv4_recv_bytes"]
        ipv6_send_bytes = self._b["ipv6_send_bytes"]
        ipv6_recv_bytes = self._b["ipv6_recv_bytes"]

        ipv6_send_bytes.items_lookup_and_delete_batch()
        ipv6_recv_bytes.items_lookup_and_delete_batch()

        # Group traffic by namespaces
        for data, collected_bytes in ipv4_send_bytes.items_lookup_and_delete_batch():
            meta = to_ipv4_key(data)
            namespace_metrics = self._metrics.get_namespace_metrics(meta.localAddr)
            dest_network = namespace_metrics.add_traffic(meta.remoteAddr, collected_bytes,
                                                         lambda m, data_count: m.add_transmitted(data_count))
            self._log_traffic(namespace_metrics, meta, dest_network, 'sent')

        for data, collected_bytes in ipv4_recv_bytes.items_lookup_and_delete_batch():
            meta = to_ipv4_key(data)
            namespace_metrics = self._metrics.get_namespace_metrics(meta.localAddr)
            dest_network = namespace_metrics.add_traffic(meta.remoteAddr, collected_bytes,
                                                         lambda m, data_count: m.add_received(data_count))
            self._log_traffic(namespace_metrics, meta, dest_network, 'received')

        # Now export the data
        values = ValueSet(labels=[self._namespace_label, 'dest_network', 'direction'])
        for value in self._metrics.metrics.values():
            namespace = value.namespace
            for network, metrics in value.metrics.items():
                net_name = network.name
                assert isinstance(metrics, NetworkMetrics)
                values.add(Value(label_values=[namespace, net_name, 'received'], value=metrics.received_bytes))
                values.add(Value(label_values=[namespace, net_name, 'sent'], value=metrics.transmitted_bytes))

        return values

    def _log_traffic(self, namespace_metrics: NamespaceNetworkMetric, meta: TCPSessionKey, dest_network: NamedNetworks,
                     direction: str):
        if self._traffic_log_mode is None:
            return

        if self._traffic_log_mode == 'unknown':
            is_unknown_traffic = namespace_metrics.is_catch_all() or dest_network.catch_all
            if not is_unknown_traffic:
                return

        self.log.info(f'Traffic: local {ipaddress.IPv4Network(meta.localAddr)}, '
                      f'remote {ipaddress.IPv4Network(meta.remoteAddr)}, '
                      f'direction {direction}, '
                      f'from process {meta.name}, catch all {namespace_metrics.is_catch_all()}')


class TCPSessionKey(NamedTuple):
    pid: int
    name: str
    localAddr: int
    localPort: int
    remoteAddr: int
    remotePort: int


def to_ipv4_key(k) -> TCPSessionKey:
    return TCPSessionKey(pid=k.pid,
                         name=k.name,
                         localAddr=swap32(k.saddr),
                         localPort=k.lport,
                         remoteAddr=swap32(k.daddr),
                         remotePort=k.dport)


def to_ipv6_key(k) -> TCPSessionKey:
    print(str(k.saddr))
    return TCPSessionKey(pid=k.pid,
                         name=k.name,
                         localAddr=k.saddr,
                         localPort=k.lport,
                         remoteAddr=k.daddr,
                         remotePort=k.dport)


def swap32(x: int) -> int:
    return int.from_bytes(x.to_bytes(4, byteorder='big'), byteorder='little', signed=False)


class NamespaceNetworkMetric:
    def __init__(self, name: str, known_networks: List[NamedNetworks], catch_all: bool = False):
        self.namespace: str = name
        self._known_networks: List[NamedNetworks] = known_networks

        self.metrics: Dict[NamedNetworks, NetworkMetrics] = dict()
        """
        Holds the send/received bytes grouped by destination network
        """

        self._is_catch_all = catch_all

    def add_traffic(self, remote_addr: int, data_bytes: int,
                    assign: Callable[[NetworkMetrics, int], None]) -> Optional[NamedNetworks]:
        """
        Adds traffic metrics for the given remote address to this namespace
        :param remote_addr: Remote ip address
        :param data_bytes: Number of bytes to add
        :param assign: Lambda for assigning the traffic to the correct metric field
        :return: The network that matched the destination
        """
        for dest_network in self._known_networks:
            if not dest_network.contains(remote_addr):
                continue
            if dest_network not in self.metrics:
                self.metrics[dest_network] = NetworkMetrics()
            assign(self.metrics[dest_network], data_bytes)
            return dest_network
        return None

    def is_catch_all(self) -> bool:
        """
        Indicates if this network is a "catch-all" or "unknown" network segment
        :return:
        """
        return self._is_catch_all


class NamespacesMetrics:
    CATCH_ALL_NAME = 'unknown'

    def __init__(self, known_networks: List[NamedNetworks]):
        self.metrics: Dict[str, NamespaceNetworkMetric] = {
            self.CATCH_ALL_NAME: NamespaceNetworkMetric(self.CATCH_ALL_NAME, known_networks, catch_all=True)
        }

        self._known_networks: List[NamedNetworks] = known_networks

        """
        Holds the send/received bytes grouped by namespace
        """
        self._container_networks: List[NamedNetworks] = []

    def get_namespace_metrics(self, local_address: int) -> NamespaceNetworkMetric:
        network = self._get_container_network(local_address)
        if network is None:
            # The local networks is not known to k8s, maybe the source is one of the known networks?
            # This happens for example for cross-node traffic
            network = self._get_known_network(local_address)
            if network is None:  # No idea what this traffic is
                return self.metrics[self.CATCH_ALL_NAME]

        if network.name not in self.metrics:
            self.metrics[network.name] = NamespaceNetworkMetric(network.name, self._known_networks)
        return self.metrics[network.name]

    def update_networks(self):
        """
        Updates the networks list based on the containers running on this node
        """
        namespaces = ContainerNetworkUtils.get_namespace_ips()
        networks = []
        for namespace, ips in namespaces.items():
            networks.append(NamedNetworks(namespace, list(ips)))
        self._container_networks = networks

    def _get_container_network(self, local_address: int) -> Optional[NamedNetworks]:
        for network in self._container_networks:
            if network.contains(local_address):
                return network
        return None

    def _get_known_network(self, local_address: int) -> Optional[NamedNetworks]:
        for network in self._known_networks:
            if network.contains(local_address):
                return network
        return None
