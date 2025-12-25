"""
Collects data from viessmann devices.
This requires a viessmann account
"""
from __future__ import annotations

import re
from typing import Optional, List, Dict

from pollect.core.ValueSet import ValueSet, Value
from pollect.libs.viessmann.ViessmannApi import ViessmannApi, ViessmannOauth, Device
from pollect.sources.Source import Source


class ViessmannSource(Source):
    AUTH_FILE = 'viessmann_token.json'

    CIRCUIT_PATTERN = re.compile(r"heating\.circuits\.(\d+)\.(.+)")
    COMPRESSOR_PATTERN = re.compile(r"heating\.compressors\.(\d+)\.(.+)")

    def __init__(self, config):
        super().__init__(config)
        client_id = config.get('client_id')
        callback_url = config.get('callback_url')
        self._auth = ViessmannOauth(client_id, callback_url, self.AUTH_FILE)
        self.api = ViessmannApi(self._auth)

    def _probe(self) -> Optional[ValueSet] | List[ValueSet]:
        try:
            self._auth.get_token()
        except ValueError:
            self.log.warning('Did not find any auth token, starting manually authorization flow')
            self._auth.authorize()

        gateways = self.api.get_gateways()
        install_id = gateways[0].installation_id
        gateway = gateways[0]
        gateway_serial = gateway.serial
        device_id = '0'
        # Search for correct device id
        for dev in gateway.devices:
            if dev.device_type != Device.TYPE_VITOCONNECT:
                device_id = dev.id
                break

        features = self.api.get_features(install_id, gateway_serial, device_id)

        # Aliases to be backward compatible
        aliases: Dict[str, str] = {
            'heating.sensors.temperature.return': 'return_temperature',
            'heating.sensors.temperature.outside': 'outside_temperature',
            'heating.dhw.sensors.temperature.hotWaterStorage.top': 'hot_water_storage_top',
            'heating.dhw.sensors.temperature.hotWaterStorage': 'hot_water_storage',
            'heating.secondaryCircuit.temperature.return.minimum': 'secondary_return_temp',
            'heating.secondaryCircuit.sensors.temperature.supply': 'secondary_supply_temp',
            'heating.dhw.charging': 'hot_water_charging',
            'heating.dhw.pumps.circulation': 'hot_water_circulation_pump',
            'heating.dhw.pumps.primary': 'hot_water_primary_pump',
            'heating.dhw.temperature.main': 'hot_water_target_temp',
        }

        main_set = ValueSet()
        circuit_set = ValueSet(labels=['circuit'])
        circuit_set.name = "heating.circuit"
        compressor_set = ValueSet(labels=['compressor'])
        compressor_set.name = 'heating.compressor'
        compressor_phase_set = ValueSet(labels=['phase', 'compressor'])
        compressor_phase_set.name = 'heating.compressor'

        for feature in features.features:
            target_set = main_set
            label_values = []
            feature_name = feature.feature
            if feature_name in aliases:
                feature_name = aliases[feature_name]

            # Group by circuit or compressor number
            # so we can label the data correctly
            match = self.CIRCUIT_PATTERN.match(feature_name)
            if match:
                target_set = circuit_set
                label_values = [match.group(1)]
                feature_name = match.group(2)

            match = self.COMPRESSOR_PATTERN.match(feature_name)
            if match:
                target_set = compressor_set
                label_values = [match.group(1)]
                feature_name = match.group(2)

            # Some features have value and status properties
            # but the value is most important for us. Status is seen as a fallback
            prop = feature.get_property("value")
            if prop is not None:
                self._add_numeric(prop, feature_name, target_set, label_values)
                continue
            prop = feature.get_property("temperature")
            if prop is not None:
                self._add_numeric(prop, feature_name, target_set, label_values)
                continue

            prop = feature.get_property("active")
            if prop is not None:
                val_type = prop.get("type", "")
                if val_type == "boolean":
                    target_set.add(Value(prop["value"], name=feature_name, label_values=label_values))
                else:
                    self.log.warning("Unknown value type for %s: %s", feature_name, val_type)
                continue

            prop = feature.get_property("status")
            if prop is not None:
                val_type = prop.get("type", "")
                if val_type == "string":
                    # Can be on,off,notConnected,connected
                    value = prop["value"]
                    val_as_bool = value == "on" or value == "connected"
                    target_set.add(Value(val_as_bool, name=feature_name, label_values=label_values))
                continue

        load_classes = ["hoursLoadClassOne", "hoursLoadClassTwo", "hoursLoadClassThree", "hoursLoadClassFour", "hoursLoadClassFive"]
        compressor_phases = [  # Compressor phases mapped to the on/off state
            ("preparing", False),
            ("heating", True),
            ("pause", False),
            ("cooling", True),
            ("preparing-defrost", False),
            ("defrost", True),
            ("passive-defrost", False),
            ("off", False),
        ]
        for comp in range(0, 2):
            comp_feature = features.get_feature(f'heating.compressors.{comp}')
            if comp_feature is not None:
                compressor_phase = comp_feature.get_property_value('phase')
                if compressor_phase is not None:
                    comp_on = False
                    for phase in compressor_phases:
                        phase_name = phase[0]
                        is_active_phase = phase_name == compressor_phase
                        compressor_phase_set.add(Value(is_active_phase,
                                                       name='phase', label_values=[phase_name, str(comp)]))
                        if is_active_phase:
                            comp_on = phase[1]

                    compressor_set.add(Value(comp_on, name='active', label_values=[str(comp)]))

            compressor_stats = features.get_feature(f'heating.compressors.{comp}.statistics')
            if compressor_stats is not None:
                comp_starts = compressor_stats.get_property_value('starts')
                if comp_starts is not None:
                    compressor_set.add(Value(comp_starts, name='stats_starts', label_values=[str(comp)]))

                comp_hours = compressor_stats.get_property_value('hours')
                if comp_hours is not None:
                    compressor_set.add(Value(comp_hours, name='stats_hours', label_values=[str(comp)]))

            compressor_stats_load = features.get_feature(f'heating.compressors.{comp}.statistics.load')
            if compressor_stats_load is not None:
                for load_class_idx in range(len(load_classes)):
                    load_class = load_classes[load_class_idx]
                    comp_hours = compressor_stats_load.get_property_value(load_class)
                    if comp_hours is not None:
                        compressor_set.add(Value(comp_hours, name='stats_hours_class_' + str(load_class_idx + 1),
                                                 label_values=[str(comp)]))

        return [main_set, compressor_phase_set, compressor_set]

    def _add_numeric(self, prop: Dict[str, any], feature_name: str, main_set: ValueSet, label_values: List[str]):
        val_type = prop.get("type", "")
        if val_type == "string":
            # Simply ignore
            return
        if val_type == "number":
            main_set.add(Value(prop["value"], name=feature_name, label_values=label_values))
            return

        self.log.warning("Unknown value type for %s: %s", feature_name, val_type)


if __name__ == '__main__':
    source = ViessmannSource({"type": "", "client_id": "f1fee4360eb9942fa542295b4ee123bf", "callback_url": ""})
    out = source.probe()
    print(str(out))
