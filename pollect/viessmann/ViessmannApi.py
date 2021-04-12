from __future__ import annotations

import json
import re
import time
from typing import Dict, Optional

import requests


class DataEntity:
    def __init__(self, data):
        self.data_classes = data.get('class', [])
        self.properties = data.get('properties', {})
        self.entities = [DataEntity(x) for x in data.get('entities', [])]
        self.links = data.get('links', [])
        self.actions = data.get('actions', [])

    def get_entity(self, class_str: str) -> Optional[DataEntity]:
        for entity in self.entities:
            if class_str in entity.data_classes:
                return entity
        return None

    def get_id(self) -> int:
        return self.properties['id']

    def get_property(self, key: str):
        return self.properties.get(key)

    def get_property_value(self, key: str):
        value_data = self.get_property(key)
        return value_data['value']

    def get_action(self, name: str):
        for action in self.actions:
            if action['name'] == name:
                return action
        return None


class Installation(DataEntity):
    def __init__(self, data):
        super().__init__(data)
        if 'model.installation' not in self.data_classes:
            raise ValueError('Invalid data class: ' + str(self.data_classes))

    def get_gateway(self) -> DataEntity:
        return self.get_entity('model.gateway')


class OAuthToken:
    """
    Represents an oauth token
    """

    access_token: str = ''
    refresh_token: str = ''
    token_type: str = ''
    expires_in: int = 0
    """
    Timestamp in seconds
    """

    def __init__(self, data):
        if data is not None:
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']
            self.token_type = data['token_type']
            self.expires_in = int(time.time()) + data['expires_in']

    def is_expired(self) -> bool:
        return self.expires_in <= int(time.time())

    @staticmethod
    def load(path: str) -> OAuthToken:
        with open(path, 'r') as file:
            data = json.load(file)
        token = OAuthToken(None)
        token.__dict__.update(data)
        return token

    def persist(self, path: str):
        with open(path, 'w') as file:
            json.dump(self.__dict__, file)


class ViessmannApi:
    # These settings are from the ViCare app
    CLIENT_ID = '79742319e39245de5f91d15ff4cac2a8'
    SECRET = '8ad97aceb92c5892e102b093c7c083fa'
    API_KEY = 'token 38c97795ed8ae0ec139409d785840113bb0f5479893a72997932d447bd1178c8'
    SCOPE = 'offline_access'
    CALLBACK_URL = 'vicare://oauth-callback/everest'

    AUTH_URL = 'https://iam.viessmann.com/idp/v1/authorize'
    TOKEN_URL = 'https://iam.viessmann.com/idp/v1/token'

    API_URL = 'https://api.viessmann-platform.io'

    _token: Optional[OAuthToken] = None

    def use_token(self, token: OAuthToken):
        """
        Uses the given token. If the token has expired, a new token will be
        requested automatically
        :param token: Token
        """
        if token.is_expired():
            token = self._refresh_token(token)
        self._token = token

    def get_token(self) -> OAuthToken:
        """
        Return the current token
        :return: Token
        """
        return self._token

    def login(self, user: str, password: str) -> OAuthToken:
        """
        Logs in using the given user and password
        :param user: User
        :param password: Password
        :return: Token
        """
        url = ViessmannApi.AUTH_URL + '?client_id=' + ViessmannApi.CLIENT_ID + \
              '&scope=' + ViessmannApi.SCOPE + \
              '&redirect_uri=' + ViessmannApi.CALLBACK_URL + \
              '&response_type=code'

        reply = requests.post(url,
                              auth=(user, password),
                              headers={
                                  'x-api-key': ViessmannApi.API_KEY
                              },
                              allow_redirects=False)

        # Example: 'vicare://oauth-callback/everest?code=Bi52fRn554t3moxGtXwAcKsq-KLd1NnrrMHwdflaXW4'
        location = reply.headers.get('location')
        match = re.match(r'.+?code=(.+)', location)
        if not match:
            raise ValueError('Could not extract code from ' + location)
        code = match.group(1)

        token = self._get_token_from_code(code)
        return token

    def get_installations(self):
        reply = self._get('/general-management/installations')
        installations = reply.get('entities', [])
        return [Installation(x) for x in installations]

    def get_features(self, installation_id: int, gateway_serial: str, device_id: int) -> DataEntity:
        data = self.get_operational_data(installation_id, gateway_serial, device_id, '/features')
        return DataEntity(data)

    def get_operational_data(self, installation_id: int, gateway_serial: str, device_id: int, path: str):
        data = self._get('/operational-data/installations/' + str(installation_id) +
                         '/gateways/' + gateway_serial +
                         '/devices/' + str(device_id) +
                         path)
        return data

    def execute_action(self, action, data: Dict[str, any]):
        method = action['method']
        href = action['href']
        self._exec(method, href, data)
        # const result: Either<string, boolean> = await client.executeAction('heating.circuits.0.operating.programs.comfort', 'setTemperature', {targetTemperature: 22});

    @staticmethod
    def _refresh_token(token: OAuthToken) -> OAuthToken:
        token_config = {
            'grant_type': 'refresh_token',
            'refresh_token': token.refresh_token,
        }
        reply = requests.post(ViessmannApi.TOKEN_URL, data=token_config,
                              auth=(ViessmannApi.CLIENT_ID, ViessmannApi.SECRET))

        if reply.status_code != 200:
            raise ValueError('Could not refresh token from code: ' + reply.text)
        return OAuthToken(reply.json())

    @staticmethod
    def _get_token_from_code(code: str) -> OAuthToken:
        token_config = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': ViessmannApi.CALLBACK_URL,
            'client_id': ViessmannApi.CLIENT_ID,
            'client_secret': ViessmannApi.SECRET,
            'scope': ViessmannApi.SCOPE,
        }
        reply = requests.post(ViessmannApi.TOKEN_URL, data=token_config,
                              auth=(ViessmannApi.CLIENT_ID, ViessmannApi.SECRET))
        if reply.status_code != 200:
            raise ValueError('Could not get access token from code: ' + reply.text)
        return OAuthToken(reply.json())

    def _get(self, path: str) -> Dict[str, any]:
        """
        Calls the API at the given path
        :param path: Path
        :return: Data
        """
        return self._exec('get', ViessmannApi.API_URL + path)

    def _exec(self, method_type: str, href: str, payload=None):
        if method_type.lower() == 'get':
            reply = requests.get(href, headers=self._get_headers())
        elif method_type.lower() == 'post':
            reply = requests.post(href, headers=self._get_headers(), json=payload)
        else:
            raise ValueError('Invalid method: ' + method_type)

        if reply.status_code > 299 or reply.status_code < 200:
            raise ValueError('Invalid reply for ' + href + ': ' + reply.text)
        if reply.status_code == 204:
            return {}
        return reply.json()

    def _get_headers(self) -> Dict[str, str]:
        """
        Returns the headers which should be used for regular requests
        :return: Headers
        """
        return {
            'Authorization': 'Bearer ' + self._token.access_token,
        }
