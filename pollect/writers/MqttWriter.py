from __future__ import annotations

import json
import re
from typing import List, Optional

import paho.mqtt.client as mqtt

from pollect.core.ValueSet import ValueSet
from pollect.sources.Source import Source
from pollect.writers.Writer import Writer


class MqttWriter(Writer):
    _port: int
    _host: str
    _client: mqtt.Client
    _includes: set[re.Pattern]

    hass_discovery_prefix: str = "homeassistant"

    def __init__(self, config):
        super().__init__(config)
        self._host = self.config.get('host', '127.0.0.1')
        self._port = self.config.get('port', 1883)
        self._user = config.get('user')
        self._password = config.get('password')
        self._includes = set()

        for path in config.get('includePattern', []):
            self._includes.add(re.compile(path))

        self._ha_autodiscovery = self.config.get('hassAutodiscovery', False)
        self._discovery_sent = {}

    def supports_partial_write(self) -> bool:
        return True

    def start(self):
        self._client = mqtt.Client(client_id='pollect')
        self._client.on_connect_fail = self._on_connect_fail
        if self._password is not None:
            self._client.username_pw_set(self._user, self._password)
        self._client.connect_async(self._host, self._port, keepalive=30)
        self._client.loop_start()

    def stop(self):
        self._client.disconnect()

    def _on_connect_fail(self):
        self.log.error(f'Connection failed')

    def write(self, data: List[ValueSet], source_ref: Optional[Source] = None):
        if not self._client.is_connected():
            self.log.warning('Not connected to mqtt broker')
            return
        for value_set in data:
            for value_obj in value_set.values:
                path = value_set.name
                if value_obj.name is not None:
                    path += '/' + value_obj.name
                for x in range(len(value_set.labels)):
                    path += '/' + value_set.labels[x] + '/' + value_obj.label_values[x]
                path = path.lower()

                if len(self._includes) > 0:
                    included = False
                    for pattern in self._includes:
                        if pattern.fullmatch(path):
                            included = True
                            break
                    if not included:
                        continue

                if self._ha_autodiscovery and path not in self._discovery_sent:
                    self._send_discovery(value_obj.name, path)

                self.log.debug('Publishing message: %s', path)
                self._client.publish(path, value_obj.value, retain=True)

    def _send_discovery(self, name: str, path: str):
        discovery_msg = {
            'name': name,
            'device_class': None,
            'state_topic': name
        }
        object_id = path.replace('/', '_')
        self._client.publish(self.hass_discovery_prefix + '/sensor/' + object_id + '/config',
                             json.dumps(discovery_msg),
                             retain=True)
        self._discovery_sent[path] = True
