import datetime
import os
import subprocess
from datetime import datetime
from typing import Optional, List
from urllib.parse import urlparse

import OpenSSL

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class CertificateSource(Source):
    """
    Checks the expiration date of certificates
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

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        value_set = ValueSet()
        expire_days = self.get_expire_days(self.host, self.port)
        value_set.add(Value(expire_days, name='cert_expire_days'))
        return value_set

    @staticmethod
    def get_expire_days(host: str, port: int) -> int:
        args = ['openssl', 's_client', '-connect',
                host + ':' + str(port), '-servername', host,
                '-certform', 'pem']
        if os.name == 'nt':
            args.insert(0, 'wsl')

        p = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        p.stdin.write(b'Q\n')
        stdout = p.communicate()[0]
        stdout_str = stdout.decode('utf-8')
        start_found = False
        cert = []
        for line in stdout_str.split('\n'):
            if '-----BEGIN CERTIFICATE-----' in line:
                start_found = True
                cert.append(line)
                continue
            if not start_found:
                continue
            if '-----END CERTIFICATE-----' in line:
                cert.append(line)
                break
            cert.append(line)

        x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, '\n'.join(cert).encode('utf-8'))
        ts = x509.get_notAfter().decode('utf-8')[:-1]
        parsed_ts = datetime.strptime(ts, '%Y%m%d%H%M%S')
        return int((parsed_ts - datetime.now()).total_seconds() / 60 / 60 / 24)
