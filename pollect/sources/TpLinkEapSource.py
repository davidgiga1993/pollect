import hashlib
import os
from typing import Optional, List
from urllib.parse import urlparse

import requests

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class TpLinkEapSource(Source):
    """
    Collects statistics data from TP-Link EAP access points.
    """

    SID_FILE = 'tp_link_sid.tmp'

    def __init__(self, config):
        super().__init__(config)
        self._url = config['url']
        self._domain = urlparse(self._url).netloc

        self._user = config['user']
        self._pass = config['password']
        self._session = requests.Session()

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        ap_data = self._get('/data/monitor.ap.aplist.json?operation=load')
        aps = ap_data['data']
        ap = aps[0]

        mac = ap['MAC']
        value_sets = []

        total_clients = ap['StaNum']
        value_set = ValueSet()
        value_set.add(Value(total_clients, name='total_clients'))
        value_sets.append(value_set)

        value_set = ValueSet(labels=['wifi', 'direction'])
        value_sets.append(value_set)
        url_safe_mac = mac.replace(':', '%3A')
        self._update_wifi_stats(value_set, '2ghz', 'WIFI0', url_safe_mac)
        self._update_wifi_stats(value_set, '5ghz', 'WIFI1', url_safe_mac)
        return value_sets

    def _get(self, path: str, depth: int = 0):
        """
        Executes a GET call to the api endpoint at the given path
        :param path: Path
        :param depth: Call depth
        :return: Data
        """
        reply = self._session.get(self._url + path, headers={
            # Required as otherwise the API won't return data
            'Referer': self._url
        })

        data = reply.json()
        timeout = data.get('timeout')
        if timeout is None or timeout == 'false':
            # Login still valid
            return data
        if depth > 0:
            # Login was not possible
            raise ValueError('Session expired and re-login failed')

        self._login()
        self._get(path, depth + 1)

    def _login(self):
        if os.path.isfile(self.SID_FILE):
            with open(self.SID_FILE) as file:
                sid = file.readline()
            # Verify SID
            self._session.cookies.set('COOKIE', sid, domain=self._domain)
            self._get('/data/monitor.ap.aplist.json?operation=load')
            return

            # Get index page to get a cookie assigned
        reply = self._session.get(self._url)
        if reply.status_code != 200:
            raise ValueError('Could not load index page at ' + self._url + ', is it correct?')

        # Now login
        reply = self._session.post(self._url, data={
            'username': self._user,
            'password': self._md5(self._pass).upper(),
        })
        if reply.status_code != 200:
            raise ValueError('Could not login: ' + str(reply.status_code))

        # Persist SID
        sid = self._session.cookies['COOKIE']
        with open(self.SID_FILE, 'w') as file:
            file.write(sid)

    @staticmethod
    def _md5(value: str) -> str:
        md5 = hashlib.md5()
        md5.update(value.encode())
        return md5.hexdigest()

    def _update_wifi_stats(self, value_set: ValueSet, metric_name: str, wifi_name: str, url_safe_mac: str):
        data = self._get('/data/monitor.ap.interface.json?'
                         'operation=read'
                         '&interface=' + wifi_name +
                         '&apMac=' + url_safe_mac)

        wifi_data = data['data']
        value_set.add(Value(wifi_data['rx_packets'], name='packets', label_values=[metric_name, 'rx']))
        value_set.add(Value(wifi_data['tx_packets'], name='packets', label_values=[metric_name, 'tx']))
        value_set.add(Value(wifi_data['rx_bytes'], name='bytes', label_values=[metric_name, 'rx']))
        value_set.add(Value(wifi_data['tx_bytes'], name='bytes', label_values=[metric_name, 'tx']))
        value_set.add(Value(wifi_data['rx_errors'], name='errors', label_values=[metric_name, 'rx']))
        value_set.add(Value(wifi_data['tx_errors'], name='errors', label_values=[metric_name, 'tx']))
