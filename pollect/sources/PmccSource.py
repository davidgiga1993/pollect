import base64
import json
import time
from typing import Optional, List, Dict

import requests

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class PmccSource(Source):
    def __init__(self, config):
        super().__init__(config)
        self._url = config.get('url')
        self._password = config.get('password')

        self._s = requests.session()

        self._expiry: int = 0

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        self._login()

        general = ValueSet()
        temperature = ValueSet(labels=['sensor'])
        temperature.name = 'temp'
        errors = ValueSet(labels=['code'])
        errors.name = 'errors'

        cpu_temp = self._get('/v1/api/SelfTest/Temp_CPU/properties')['temperature']
        temperature.add(Value(cpu_temp, label_values=['cpu']))

        free_memory = self._get('/v1/api/SelfTest/RAM/properties')['ramFree']
        general.add(Value(free_memory, name='free_memory'))

        emcc = self._get('/v1/api/SelfTest/EMMC/properties')
        general.add(Value(emcc['PersistencyFreeSpace'], name='free_space_persistent_storage'))
        general.add(Value(emcc['SystemFreeSpace'], name='free_space_system_storage'))

        canbus = self._get('/v1/api/iCAN/properties')
        general.add(Value(canbus['propM4TempLCD'], name='temp_lcd'))

        temp_data = json.loads(canbus['propjIcanTempChanged'])
        temperature.add(Value(temp_data['Internal_Micro'], label_values=['uc']))
        temperature.add(Value(temp_data['Internal_Relay'], label_values=['relay1']))
        temperature.add(Value(temp_data['Internal_Relay_2'], label_values=['relay2']))

        # Collect error codes
        error_map = {
            0x401026: 'v2g_timeout'
        }
        error_states = {}
        for key, value in error_map.items():
            error_states[value] = 0

        event_storage = self._put('/v1/api/DTCHandler/methods/GetDTCs', nested_json=True)
        for error_code in event_storage['active_dtcs']:
            if error_code in error_map:
                error_states[error_map[error_code]] = 1

        for key, value in error_states.items():
            errors.add(Value(value, label_values=[key]))
        return [general, temperature, errors]

    def _get(self, path: str, nested_json: bool = False) -> Dict[str, any]:
        return self._exec("GET", path, nested_json)

    def _put(self, path: str, nested_json: bool = False) -> Dict[str, any]:
        return self._exec("PUT", path, nested_json)

    def _exec(self, method: str, path: str, nested_json: bool = False, depth: int = 0) -> Dict[str, any]:
        reply = self._s.request(method, self._url + path, verify=False)
        if reply.status_code == 403:
            if depth > 2:
                raise ValueError(f'Could not retrieve {path} due to {reply.status_code} {reply.content}')
            self._login()
            return self._exec(method, path, nested_json, depth + 1)

        data = reply.json()
        if nested_json:
            return json.loads(data)
        return data

    def _login(self):
        now = time.time()
        expires_in = (now - self._expiry)
        if self._expiry != 0:
            if expires_in > 180:  # Still valid for at least 3min
                return
            if expires_in > 10:  # Still valid for 10 sec, try renew
                reply = self._s.get(f'{self._url}/jwt/refresh', verify=False)
                if reply.status_code == 200:
                    self._handle_login_reply(reply)
                    return

        reply = self._s.post(f'{self._url}/jwt/login', data={
            'user': 'technician',
            'pass': self._password
        }, verify=False, headers={
            'Referer': self._url,
        })
        if reply.status_code != 200:
            raise ValueError(f'Could not login: {reply.status_code}: {reply.text}')

        self._handle_login_reply(reply)

    def _handle_login_reply(self, reply: requests.Response):
        token = reply.json()['token']
        self._parse_jwt(token)
        self._s.headers = {'Authorization': f'Bearer {token}',
                           'Referer': self._url,
                           }

    def _parse_jwt(self, token: str):
        parts = token.split('.')
        if len(parts) < 3:
            raise ValueError('Invalid JWT')

        base64_str = parts[1]
        # Add padding for python base64 decode to work...
        base64_str += "=" * ((4 - len(base64_str) % 4) % 4)
        json_str = base64.b64decode(base64_str)
        jwt_content = json.loads(json_str)
        self._expiry = jwt_content['exp']

