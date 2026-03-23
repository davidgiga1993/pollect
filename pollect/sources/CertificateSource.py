import datetime
import socket
from datetime import datetime
from typing import Optional, List
from urllib.parse import urlparse

from OpenSSL import SSL

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class CertificateSource(Source):
    """
    Checks the expiration date of certificates.
    WThe certs for all IPs behind the hostname/ DNS entry will be checked
    """

    def __init__(self, config):
        super().__init__(config)
        self.host = config.get('host')
        self.port = config.get('port')
        url = config.get('url')
        if url is not None:
            parsed_url = urlparse(url)
            self.host = str(parsed_url.hostname)
            self.port = parsed_url.port
            if self.port is None:
                if parsed_url.scheme == 'https':
                    self.port = 443
                elif parsed_url.scheme == 'http':
                    self.port = 80

    def _probe(self) -> Optional[ValueSet] | List[ValueSet]:
        value_set = ValueSet(['ip'])

        ips = self._resolve_host()
        for ip in ips:
            expiration_days = self.get_expiration_in_days(self.host, ip, self.port)
            value_set.add(Value(expiration_days, label_values=[ip], name='cert_expire_days'))
        return value_set

    def _resolve_host(self) -> List[str]:
        entries = socket.getaddrinfo(self.host, port=self.port, family=socket.AF_INET, proto=socket.IPPROTO_TCP)
        # Get IP from addrinfo
        return [x[4][0] for x in entries]

    @staticmethod
    def get_expiration_in_days(hostname: str, ip_addr: str, port: int) -> int:
        context = SSL.Context(method=SSL.SSLv23_METHOD)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssl_conn = SSL.Connection(context=context, socket=sock)
        ssl_conn.set_tlsext_host_name(hostname.encode())
        ssl_conn.settimeout(5)
        ssl_conn.connect((ip_addr, port))
        ssl_conn.setblocking(1)
        ssl_conn.do_handshake()
        peer_cert = ssl_conn.get_peer_certificate()

        ts = peer_cert.get_notAfter().decode('utf-8')[:-1]
        parsed_ts = datetime.strptime(ts, '%Y%m%d%H%M%S')
        return int((parsed_ts - datetime.now()).total_seconds() / 60 / 60 / 24)
