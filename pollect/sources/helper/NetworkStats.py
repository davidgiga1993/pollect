import datetime
import ipaddress


class NetworkMetrics:
    bytes_to_network: int
    bytes_from_network: int

    def __init__(self, bytes_to_network: int = 0, bytes_from_network: int = 0):
        self.bytes_to_network = bytes_to_network
        self.bytes_from_network = bytes_from_network

    def divide(self, delta):
        self.bytes_to_network = self.bytes_to_network / delta
        self.bytes_from_network = self.bytes_from_network / delta


class NetworkMetricsCounter:
    """
    Holds the count of bytes per IP subnet
    """

    def __init__(self, name: str, subnet: str):
        self.name = name
        self._subnet: ipaddress.IPv4Network = ipaddress.ip_network(subnet)
        self._netw: int = int(self._subnet.network_address)
        self._mask: int = int(self._subnet.netmask)

        self.bytes_to_network: int = 0
        self.bytes_from_network: int = 0
        self.last_reset: datetime.datetime = datetime.datetime.now()

    def contains(self, ip: int):
        return (ip & self._mask) == self._netw

    def get_per_second(self, now: datetime.datetime) -> NetworkMetrics:
        delta = (now - self.last_reset).total_seconds()
        self.last_reset = now

        metrics = NetworkMetrics(self.bytes_to_network, self.bytes_from_network)
        metrics.divide(delta)

        self.bytes_to_network = 0
        self.bytes_from_network = 0
        return metrics
