import socket
import time

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class TcpTimeSource(Source):
    """
    Source for measuring the tcp connection time
    """

    def __init__(self, config):
        super().__init__(config)
        self.host = config.get('host')
        self.port = config.get('port')
        self.timeout = config.get('timeout', 10)

    def _probe(self):
        data = ValueSet()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        try:
            start = time.time() * 1000
            self.sock.connect((self.host, self.port))
            end = time.time() * 1000
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
            data.add(Value(int(end - start)))
        except socket.timeout:
            data.add(Value(self.timeout * 1000))
        return data
