import hashlib
import hmac
import time
from typing import Dict, TypeVar, List
from urllib.parse import urlencode

import requests

from pollect.core.Log import Log
from pollect.libs.api.Serializable import Serializable
from pollect.libs.zodiac.Models import LoginReply, PoolCleanerInfo, SystemInfo

T = TypeVar('T')


class ZodiacApi(Log):
    """
    Zodiac API
    """

    API_KEY = 'EOOEMOW4YR6QNB07'
    API_SECRET_KEY = 'cj7iYKjiKxOqiLcN65PffA'

    SHADOW_URL = 'https://prod.zodiac-io.com'
    API_URL = 'https://r-api.iaqualink.net'
    PRM_URL = 'https://prm.iaqualink.net'

    user: LoginReply

    def __init__(self):
        super().__init__(__name__)
        self.user = LoginReply()

    def login(self, email: str, password: str) -> LoginReply:
        dto = self._post(f'{self.SHADOW_URL}/users/v1/login', {
            'apiKey': self.API_KEY,
            'email': email,
            'password': password,
        }, LoginReply())
        self.user = dto
        return dto

    def refresh_auth(self) -> LoginReply:
        current_refresh_token = self.user.userPoolOAuth.RefreshToken
        if current_refresh_token is None or current_refresh_token == '':
            raise ValueError("No refresh token available, can't refresh auth")

        body = {
            'email': self.user.email,
            'refresh_token': current_refresh_token
        }
        dto = self._post(f'{self.SHADOW_URL}/users/v1/refresh', body, LoginReply())
        if dto.userPoolOAuth.RefreshToken == '':
            # API didn't reply with refresh token, keep current
            self.log.warning('No new refresh token provided by api')
            dto.userPoolOAuth.RefreshToken = current_refresh_token
        self.user = dto
        return dto

    def get_device_info(self, serial_nr: str) -> PoolCleanerInfo:
        """
        Returns details about a device
        :param serial_nr:  Serial number of the device
        :return: Details
        """
        self._require_auth()
        id_token = self.user.userPoolOAuth.IdToken
        user_id = self.user.id
        url = f'{self.SHADOW_URL}/devices/v2/{serial_nr}/shadow'
        data = self._get(url, PoolCleanerInfo(), query={
            'signature': self._sign(f'{serial_nr.upper()},{user_id}'),
        }, headers={
            'Authorization': id_token
        })
        return data

    def get_system_list_v2(self) -> List[SystemInfo]:
        """
        Returns all available devices
        :return: List of devices
        """
        self._require_auth()
        unix_time = round(time.time())
        user_id = self.user.id
        id_token = self.user.userPoolOAuth.IdToken
        sign = self._sign(f'{user_id},{unix_time}')

        url = f'{self.PRM_URL}/v2/devices.json?user_id={user_id}&signature={sign}&timestamp={unix_time}'
        data = self._get(url, [SystemInfo()], headers={
            'api_key': self.API_KEY,
            'Authorization': id_token
        })
        return data

    def execute_command(self, serial_nr: str, command: str, use_v2: bool = True):
        """
        Untested - This isn't used by the tested device.
        """
        self._require_auth()
        user_id = self.user.id
        if use_v2:
            id_token = self.user.userPoolOAuth.IdToken
            url = f'{self.API_URL}/devices/v2/{serial_nr}/execute_read_command.json'
            unix_time = round(time.time())
            sign = self._sign(f'{serial_nr},{user_id},{unix_time}')
            data = self._post(url, {
                'user_id': user_id,
                'command': '/command',
                'signature': sign,
                'timestamp': unix_time,
                'params': f'request={command}&timeout=800'
            }, Serializable(), headers={
                'api_key': self.API_KEY,
                'Authorization': id_token
            })
        else:
            auth_token = self.user.authentication_token
            query_params = {
                'api_key': self.API_KEY,
                'authentication_token': auth_token,
                'user_id': user_id,
                'command': '/command',
                'params': f'request={command}&timeout=800'
            }
            url = f'https://r-api.iaqualink.net/devices/{serial_nr}/execute_read_command.json'
            data = self._post(url, {}, Serializable(), query=query_params, headers={
                "Accept": "application/json"
            })

        return data

    def _get(self, path: str, dto: T, query=None, headers=None) -> T:
        if query is not None:
            path += '?' + urlencode(query)
        reply = requests.get(path, headers=headers)
        self._handle_reply(reply)
        data = reply.json()
        return Serializable.deserialize_from_data(data, dto)

    def _post(self, path: str, payload: Dict[str, any], dto: T, query=None, headers=None) -> T:
        if query is not None:
            path += '?' + urlencode(query)
        reply = requests.post(path, json=payload, headers=headers)
        self._handle_reply(reply)
        data = reply.json()
        return Serializable.deserialize_from_data(data, dto)

    def _sign(self, content: str) -> str:
        key = bytes(self.API_SECRET_KEY, 'UTF-8')
        message = bytes(content, 'UTF-8')
        digester = hmac.new(key, message, hashlib.sha1)
        signature = digester.digest()
        return ''.join('{:02x}'.format(x) for x in signature)

    def _handle_reply(self, reply):
        if reply.status_code != 200:
            raise ValueError(f'Invalid reply: {reply.status_code} - {reply.content}')

    def _require_auth(self):
        if not self.user.is_logged_in():
            raise ValueError('User is not logged in')
        if self.user.is_expired():
            self.log.info('Auth expired, refreshing...')
            self.refresh_auth()
