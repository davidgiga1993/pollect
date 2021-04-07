"""
Collects data from viessmann devices.
This requires a viessmann account
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Optional, List, Dict

import requests

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


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
        reply = requests.get(ViessmannApi.API_URL + path, headers=self._get_headers())
        if reply.status_code != 200:
            raise ValueError('Invalid reply for ' + path + ': ' + reply.text)
        return reply.json()

    def _get_headers(self) -> Dict[str, str]:
        """
        Returns the headers which should be used for regular requests
        :return: Headers
        """
        return {
            'Authorization': 'Bearer ' + self._token.access_token,
        }


class ViessmannSource(Source):
    AUTH_FILE = 'viessmann_token.json'

    def __init__(self, config):
        super().__init__(config)
        user = config.get('user')
        password = config.get('password')
        self.api = ViessmannApi()
        if os.path.isfile(self.AUTH_FILE):
            token = OAuthToken.load(self.AUTH_FILE)
            self.api.use_token(token)
            token = self.api.get_token()
            token.persist(self.AUTH_FILE)
        else:
            token = self.api.login(user, password)
            token.persist(self.AUTH_FILE)

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:

        # A token refresh might be required
        token = self.api.get_token()
        self.api.use_token(token)
        if token.access_token != self.api.get_token().access_token:
            # Token has changed
            token.persist(self.AUTH_FILE)

        values = ValueSet()
        installations = self.api.get_installations()
        install_id = installations[0].get_id()
        gateway = installations[0].get_gateway()
        gateway_serial = gateway.get_property('serial')
        device_id = 0

        features = self.api.get_features(install_id, gateway_serial, device_id)

        # Rücklauf (hydraulische weiche)
        return_temp = features.get_entity('heating.sensors.temperature.return').get_property_value('value')
        values.add(Value(return_temp, name='return_temperature'))

        # Außentemperatur
        outside_temp = features.get_entity('heating.sensors.temperature.outside').get_property_value('value')
        values.add(Value(outside_temp, name='outside_temperature'))

        hot_water_storage_top = features.get_entity('heating.dhw.sensors.temperature.hotWaterStorage.top') \
            .get_property_value('value')
        values.add(Value(hot_water_storage_top, name='hot_water_storage_top'))

        hot_water_storage = features.get_entity('heating.dhw.sensors.temperature.hotWaterStorage') \
            .get_property_value('value')
        values.add(Value(hot_water_storage, name='hot_water_storage'))

        # Vorlauf
        supply_temp = features.get_entity('heating.circuits.0.sensors.temperature.supply').get_property_value('value')
        values.add(Value(supply_temp, name='supply_temp'))

        secondary_temp_return = features.get_entity('heating.secondaryCircuit.sensors.temperature.return') \
            .get_property_value('value')
        values.add(Value(secondary_temp_return, name='secondary_return_temp'))

        secondary_temp_supply = features.get_entity('heating.secondaryCircuit.sensors.temperature.supply') \
            .get_property_value('value')
        values.add(Value(secondary_temp_supply, name='secondary_supply_temp'))

        compressor_active = features.get_entity('heating.compressor').get_property_value('active')
        values.add(Value(compressor_active, name='compressor_active'))

        compressor_stats = features.get_entity('heating.compressors.0.statistics')
        comp_starts = compressor_stats.get_property_value('starts')
        values.add(Value(comp_starts, name='compressor_stats_starts'))

        comp_hours = compressor_stats.get_property_value('hours')
        values.add(Value(comp_hours, name='compressor_stats_hours'))

        comp_hours_class_1 = compressor_stats.get_property_value('hoursLoadClassOne')
        values.add(Value(comp_hours_class_1, name='compressor_stats_hours_class_1'))

        comp_hours_class_2 = compressor_stats.get_property_value('hoursLoadClassTwo')
        values.add(Value(comp_hours_class_2, name='compressor_stats_hours_class_2'))

        comp_hours_class_3 = compressor_stats.get_property_value('hoursLoadClassThree')
        values.add(Value(comp_hours_class_3, name='compressor_stats_hours_class_3'))

        comp_hours_class_4 = compressor_stats.get_property_value('hoursLoadClassFour')
        values.add(Value(comp_hours_class_4, name='compressor_stats_hours_class_4'))

        comp_hours_class_5 = compressor_stats.get_property_value('hoursLoadClassFive')
        values.add(Value(comp_hours_class_5, name='compressor_stats_hours_class_5'))

        heating_rod = features.get_entity('heating.heatingRod.status')
        heating_rod_on = heating_rod.get_property_value('overall')
        values.add(Value(heating_rod_on, name='heating_rod_active'))

        heating_rod_on_level1 = heating_rod.get_property_value('level1')
        values.add(Value(heating_rod_on_level1, name='heating_rod_active_level_1'))

        heating_rod_on_level2 = heating_rod.get_property_value('level2')
        values.add(Value(heating_rod_on_level2, name='heating_rod_active_level_2'))

        heating_rod_on_level3 = heating_rod.get_property_value('level3')
        values.add(Value(heating_rod_on_level3, name='heating_rod_active_level_3'))

        dhw_charging = features.get_entity('heating.dhw.charging').get_property_value('active')
        values.add(Value(dhw_charging, name='hot_water_charging'))

        heating_circulation_pump = features.get_entity('heating.circuits.0.circulation.pump') \
                                       .get_property_value('status') == 'on'
        values.add(Value(heating_circulation_pump, name='heating_circulation_pump'))

        dhw_circulation_pump = features.get_entity('heating.dhw.pumps.circulation') \
                                   .get_property_value('status') == 'on'
        values.add(Value(dhw_circulation_pump, name='hot_water_circulation_pump'))

        # Pumpe Warmwasserspeicher
        dhw_pump_primary = features.get_entity('heating.dhw.pumps.primary') \
                               .get_property_value('status') == 'on'
        values.add(Value(dhw_pump_primary, name='hot_water_primary_pump'))

        # Settings: Hot water target temperature
        hot_water_target = features.get_entity('heating.dhw.temperature').get_property_value('value')
        values.add(Value(hot_water_target, name='hot_water_target_temp'))

        return values
