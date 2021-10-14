from __future__ import annotations

import json
import os
import re
import time
from typing import Dict, Optional, List

import requests


class JsonObject:
    def __init__(self, data):
        self._data = data


class Feature(JsonObject):
    def __init__(self, data):
        super().__init__(data)
        self.feature = data['feature']  # type: str
        self.is_enabled = data['isEnabled']  # type: bool
        self.is_ready = data['isReady']  # type: bool

        self.properties = data.get('properties', {})
        self.commands = data.get('commands', {})
        self.components = data.get('components', [])
        self.links = data.get('links', [])
        self.actions = data.get('actions', [])

    def get_property(self, property_name: str):
        return self.properties.get(property_name)

    def get_property_value(self, property_name: str):
        value_data = self.get_property(property_name)
        return value_data['value']

    def get_action(self, name: str):
        for action in self.actions:
            if action['name'] == name:
                return action
        return None


class FeatureList:
    def __init__(self, data):
        self.features = [Feature(x) for x in data['data']]

    def get_feature(self, name: str) -> Feature:
        for feature in self.features:
            if feature.feature == name:
                return feature
        raise KeyError('Feature ' + name + ' not found')


class Device(JsonObject):
    TYPE_VITOCONNECT = 'vitoconnect'

    def __init__(self, data):
        super().__init__(data)
        self.id = data['id']  # type: str
        self.device_type = data['deviceType']


class Gateway(JsonObject):
    def __init__(self, data):
        super().__init__(data)
        self.serial = data['serial']
        self.version = data['version']
        self.aggregated_status = data['aggregatedStatus']
        self.devices = [Device(x) for x in data.get('devices', [])]


class Installation(JsonObject):
    def __init__(self, data):
        super().__init__(data)
        self.id = data['id']  # type: int
        self.description = data['description']
        self.updated_at = data['updatedAt']
        self.aggregated_status = data['aggregatedStatus']
        self.gateways = [Gateway(x) for x in data.get('gateways', [])]  # type: List[Gateway]


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


class ViessmannOauth:
    authorize_url = "https://iam.viessmann.com/idp/v2/authorize"
    token_url = "https://iam.viessmann.com/idp/v2/token"

    # These settings are from the ViCare app and are not used anymore
    CLIENT_ID = '79742319e39245de5f91d15ff4cac2a8'
    SECRET = '8ad97aceb92c5892e102b093c7c083fa'
    API_KEY = 'token 38c97795ed8ae0ec139409d785840113bb0f5479893a72997932d447bd1178c8'
    SCOPE = 'offline_access'
    CALLBACK_URL = 'vicare://oauth-callback/everest'

    def __init__(self, client_id: str, callback_url: str, cache_path: str):
        self._client_id = client_id
        self._callback_url = callback_url
        self._current_token = None  # type: Optional[OAuthToken]
        self._cache_path = cache_path

    def get_token(self) -> OAuthToken:
        if self._current_token is None:
            if not os.path.exists(self._cache_path):
                raise ValueError('No token defined and no token found at ' + self._cache_path +
                                 'Make sure to authorize first')
            self._current_token = OAuthToken.load(self._cache_path)

        if self._current_token.is_expired():
            self.refresh()

        return self._current_token

    def authorize(self):
        authorization_redirect_url = self.authorize_url + '?response_type=code' \
                                                          '&client_id=' + self._client_id + \
                                     '&redirect_uri=' + self._callback_url + \
                                     '&response_type=code' \
                                     '&code_challenge_method=plain' \
                                     '&code_challenge=DbyrQKpOn0Iy07u6ydCdo5XFVO4fIb7cIJW6mnLPDVc' \
                                     '&scope=IoT%20User%20offline_access'

        print("Go to the following url and enter the code from the returned url: ")
        print(authorization_redirect_url)

        authorization_code = ''
        while authorization_code == '':
            authorization_code = input('code=')
            if len(authorization_code) < 10:
                print('Invalid code, try again')
                authorization_code = ''

        data = {'grant_type': 'authorization_code',
                'client_id': self._client_id,
                'code': authorization_code,
                'redirect_uri': self._callback_url,
                'code_verifier': 'DbyrQKpOn0Iy07u6ydCdo5XFVO4fIb7cIJW6mnLPDVc',
                }
        print("Requesting access token")
        access_token_response = requests.post(self.token_url, data=data, allow_redirects=False)
        if access_token_response.status_code != 200:
            raise ValueError('Access token request failed: ' + str(access_token_response.text))

        token = OAuthToken(access_token_response.json())
        self._set_token(token)
        return token

    def refresh(self, refresh_token: str = None) -> OAuthToken:
        if refresh_token is None:
            return self.refresh(self._current_token.refresh_token)

        api_call_response = requests.post(self.token_url, data={
            'grant_type': 'refresh_token',
            'client_id': self._client_id,
            'refresh_token': refresh_token
        })
        if api_call_response.status_code != 200:
            raise ValueError('Refresh failed: ' + str(api_call_response.text))

        token = OAuthToken(api_call_response.json())
        self._set_token(token)
        return token

    def _set_token(self, token: OAuthToken):
        self._current_token = token
        token.persist(self._cache_path)

    def login(self, user: str, password: str) -> OAuthToken:
        """
        Logs in using the given user and password (deprecated!)
        :param user: User
        :param password: Password
        :return: Token
        """
        url = ViessmannOauth.authorize_url + '?client_id=' + ViessmannOauth.CLIENT_ID + \
              '&scope=' + ViessmannOauth.SCOPE + \
              '&redirect_uri=' + ViessmannOauth.CALLBACK_URL + \
              '&response_type=code'

        reply = requests.post(url,
                              auth=(user, password),
                              headers={
                                  'x-api-key': ViessmannOauth.API_KEY
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

    @staticmethod
    def _get_token_from_code(code: str) -> OAuthToken:
        """
        DEPRECATED!
        """
        token_config = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': ViessmannOauth.CALLBACK_URL,
            'client_id': ViessmannOauth.CLIENT_ID,
            'client_secret': ViessmannOauth.SECRET,
            'scope': ViessmannOauth.SCOPE,
        }
        reply = requests.post(ViessmannOauth.token_url, data=token_config,
                              auth=(ViessmannOauth.CLIENT_ID, ViessmannOauth.SECRET))
        if reply.status_code != 200:
            raise ValueError('Could not get access token from code: ' + reply.text)
        return OAuthToken(reply.json())

    @staticmethod
    def _app_refresh_token(token: OAuthToken) -> OAuthToken:
        """
        DEPRECATED!
        """
        token_config = {
            'grant_type': 'refresh_token',
            'refresh_token': token.refresh_token,
        }
        reply = requests.post(ViessmannApi.token_url, data=token_config,
                              auth=(ViessmannOauth.CLIENT_ID, ViessmannOauth.SECRET))

        if reply.status_code != 200:
            raise ValueError('Could not refresh token from code: ' + reply.text)
        return OAuthToken(reply.json())


class ViessmannApi:
    API_URL = 'https://api.viessmann.com/iot'

    def __init__(self, auth: ViessmannOauth):
        self._auth = auth

    def get_installations(self):
        reply = self._get('/v1/equipment/installations?includeGateways=true')
        installations = reply.get('data', [])
        return [Installation(x) for x in installations]

    def get_feature(self, installation_id: int, gateway_serial: str, device_id: str, feature: str) -> FeatureList:
        data = self.get_operational_data(installation_id, gateway_serial, device_id, '/features/' + feature)
        return FeatureList(data)

    def get_features(self, installation_id: int, gateway_serial: str, device_id: str) -> FeatureList:
        data = self.get_operational_data(installation_id, gateway_serial, device_id, '/features')
        return FeatureList(data)

    def get_operational_data(self, installation_id: int, gateway_serial: str, device_id: str, path: str):
        data = self._get('/v1/equipment/installations/' + str(installation_id) +
                         '/gateways/' + gateway_serial +
                         '/devices/' + device_id +
                         path)
        return data

    def execute_action(self, action, data: Dict[str, any]):
        method = action['method']
        href = action['href']
        self._exec(method, href, data)
        # const result: Either<string, boolean> = await client.executeAction('heating.circuits.0.operating.programs.comfort', 'setTemperature', {targetTemperature: 22});

    def execute_command(self, install_id: int, gateway_serial: str, device_id: str, feature_name: str,
                        command_name: str, body: dict):
        path = f'/v1/equipment/installations/{install_id}/gateways/{gateway_serial}/devices/{device_id}/features/{feature_name}'
        reply = self._exec('post', ViessmannApi.API_URL + path, {
            'commandName': command_name,
            'commandBody': body
        })
        return reply

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
        token = self._auth.get_token()
        return {
            'Authorization': 'Bearer ' + token.access_token,
        }
