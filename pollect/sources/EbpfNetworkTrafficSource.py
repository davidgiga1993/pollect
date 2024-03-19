import datetime
import os
import threading
from typing import Optional, List

import psutil
from bcc import BPF

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source
from pollect.sources.helper.NetworkStats import NetworkMetricsCounter


class EbpfNetworkTrafficSource(Source):
    """
    Collects network traffic statistics using eBPF.
    """

    MAX_MTU = 3498

    def __init__(self, config):
        super().__init__(config)
        self._running = False

        self._interface = config['interface']
        self._catch_all = NetworkMetricsCounter('other', '0.0.0.0/0')
        self._networks: List[NetworkMetricsCounter] = []
        for network in config.get('networks', []):
            name = network['name']
            net = network['network']
            self._networks.append(NetworkMetricsCounter(name, net))

    def setup(self, global_conf):
        device = self._interface
        stats = psutil.net_if_stats()
        # The MTU must be <= 3498 for the XDP program to work
        device_stats = stats.get(device)
        if device_stats is None:
            raise ValueError('Warning: Device ' + device + ' not found')

        if device_stats.mtu >= self.MAX_MTU:
            self.log.warning(f'Device {device} MTU is too large: '
                             f'{device_stats.mtu}, must be <= {self.MAX_MTU}')

        self._running = True
        threading.Thread(target=self._poll).start()

    def shutdown(self):
        self._running = False

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        values = ValueSet(labels=['network', 'direction'])
        values.name = 'bytes_per_sec'
        current_time = datetime.datetime.now()
        for network in self._networks:
            metrics = network.get_per_second(current_time)
            values.add(Value(label_values=[network.name, 'to'], value=metrics.bytes_to_network))
            values.add(Value(label_values=[network.name, 'from'], value=metrics.bytes_from_network))

        metrics = self._catch_all.get_per_second(current_time)
        values.add(Value(label_values=[self._catch_all.name, 'to'], value=metrics.bytes_to_network))

        return values

    def _poll(self):
        src_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bpf', 'core.c')

        device = self._interface
        b = BPF(src_file=src_file)

        fn = b.load_func("count_network_bytes_per_ip", BPF.XDP)
        b.attach_xdp(device, fn, 0)

        def runs_on_every_ethernet_frame(_, data, size):
            ip_and_bytes = b["events"].event(data)

            for network in self._networks:
                if network.contains(ip_and_bytes.srcIp):
                    network.bytes_from_network += ip_and_bytes.bytes
                    return
                if network.contains(ip_and_bytes.dstIp):
                    network.bytes_to_network += ip_and_bytes.bytes
                    return
            # No match
            self._catch_all.bytes_to_network += ip_and_bytes.bytes

        b["events"].open_ring_buffer(runs_on_every_ethernet_frame)
        while self._running:
            # Start polling the ring buffer for event
            b.ring_buffer_poll()

        b.remove_xdp(device, 0)
