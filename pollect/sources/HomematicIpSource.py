from typing import Optional, List

from homematicip.home import Home, TemperatureHumiditySensorDisplay

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class HomematicIpSource(Source):
    """
    Collects sensor data from homematic IP.
    Requires pip install homematicip.
    See https://homematicip-rest-api.readthedocs.io/en/latest/gettingstarted.html#installation for more details
    """

    def __init__(self, config):
        super().__init__(config)
        self._auth_token = config['authToken']
        self._access_point = config['accessPoint']
        self._home = None

    def setup(self, global_conf):
        super().setup(global_conf)
        self._home = Home()
        self._home.set_auth_token(self._auth_token)
        self._home.init(self._access_point)

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        values = ValueSet(labels=['room'])
        self._home.get_current_state()
        for group in self._home.groups:
            if group.groupType != 'META':
                continue

            room_name = self._escape_labels(group.label)
            for device in group.devices:
                if isinstance(device, TemperatureHumiditySensorDisplay):
                    # device.lastStatusUpdate
                    temp_target = device.setPointTemperature
                    temp = device.actualTemperature
                    humidity = device.humidity
                    values.add(Value(temp_target, label_values=[room_name], name='temperature_target'))
                    values.add(Value(temp, label_values=[room_name], name='temperature'))
                    values.add(Value(humidity, label_values=[room_name], name='humidity'))

        return values

    @staticmethod
    def _escape_labels(label: str) -> str:
        label = label.lower().replace('ä', 'ae') \
            .replace('ü', 'ue') \
            .replace('ö', 'oe') \
            .replace(' ', '_')
        return label
