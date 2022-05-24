"""
Collects data from viessmann devices.
This requires a viessmann account
"""
from __future__ import annotations

from typing import Optional, List

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source
from pollect.libs.viessmann.ViessmannApi import ViessmannApi, ViessmannOauth, Device


class ViessmannSource(Source):
    AUTH_FILE = 'viessmann_token.json'

    def __init__(self, config):
        super().__init__(config)
        client_id = config.get('client_id')
        callback_url = config.get('callback_url')
        self._auth = ViessmannOauth(client_id, callback_url, self.AUTH_FILE)
        self.api = ViessmannApi(self._auth)

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        try:
            self._auth.get_token()
        except ValueError:
            self.log.warning('Did not find any auth token, starting manually authorization flow')
            self._auth.authorize()

        main_set = ValueSet()
        installations = self.api.get_installations()
        install_id = installations[0].id
        gateway = installations[0].gateways[0]
        gateway_serial = gateway.serial
        device_id = '0'
        # Search for correct device id
        for dev in gateway.devices:
            if dev.device_type != Device.TYPE_VITOCONNECT:
                device_id = dev.id
                break

        features = self.api.get_features(install_id, gateway_serial, device_id)

        # Rücklauf (hydraulische weiche)
        return_temp = features.get_feature('heating.sensors.temperature.return').get_property_value('value')
        main_set.add(Value(return_temp, name='return_temperature'))

        # Außentemperatur
        outside_temp = features.get_feature('heating.sensors.temperature.outside').get_property_value('value')
        main_set.add(Value(outside_temp, name='outside_temperature'))

        hot_water_storage_top = features.get_feature('heating.dhw.sensors.temperature.hotWaterStorage.top') \
            .get_property_value('value')
        main_set.add(Value(hot_water_storage_top, name='hot_water_storage_top'))

        hot_water_storage = features.get_feature('heating.dhw.sensors.temperature.hotWaterStorage') \
            .get_property_value('value')
        main_set.add(Value(hot_water_storage, name='hot_water_storage'))

        # Vorlauf
        supply_temp = features.get_feature('heating.circuits.0.sensors.temperature.supply').get_property_value('value')
        main_set.add(Value(supply_temp, name='supply_temp'))

        try:
            secondary_temp_return = features.get_feature('heating.secondaryCircuit.sensors.temperature.return') \
                .get_property_value('value')
            main_set.add(Value(secondary_temp_return, name='secondary_return_temp'))
        except KeyError as e:
            self.log.info(str(e))

        secondary_temp_supply = features.get_feature('heating.secondaryCircuit.sensors.temperature.supply') \
            .get_property_value('value')
        main_set.add(Value(secondary_temp_supply, name='secondary_supply_temp'))

        compressor_phase = features.get_feature('heating.compressors.0').get_property_value('phase')
        main_set.add(Value(compressor_phase != 'off' and compressor_phase != 'pause', name='compressor_active'))

        compressor_phase_set = ValueSet(labels=['phase'])
        compressor_phase_set.add(Value(compressor_phase == 'cooling',
                                       name='compressor_phase', label_values=['cooling']))
        compressor_phase_set.add(Value(compressor_phase == 'heating',
                                       name='compressor_phase', label_values=['heating']))
        compressor_phase_set.add(Value(compressor_phase == 'pause',
                                       name='compressor_phase', label_values=['pause']))

        compressor_stats = features.get_feature('heating.compressors.0.statistics')
        comp_starts = compressor_stats.get_property_value('starts')
        main_set.add(Value(comp_starts, name='compressor_stats_starts'))

        comp_hours = compressor_stats.get_property_value('hours')
        main_set.add(Value(comp_hours, name='compressor_stats_hours'))

        comp_hours_class_1 = compressor_stats.get_property_value('hoursLoadClassOne')
        main_set.add(Value(comp_hours_class_1, name='compressor_stats_hours_class_1'))

        comp_hours_class_2 = compressor_stats.get_property_value('hoursLoadClassTwo')
        main_set.add(Value(comp_hours_class_2, name='compressor_stats_hours_class_2'))

        comp_hours_class_3 = compressor_stats.get_property_value('hoursLoadClassThree')
        main_set.add(Value(comp_hours_class_3, name='compressor_stats_hours_class_3'))

        comp_hours_class_4 = compressor_stats.get_property_value('hoursLoadClassFour')
        main_set.add(Value(comp_hours_class_4, name='compressor_stats_hours_class_4'))

        comp_hours_class_5 = compressor_stats.get_property_value('hoursLoadClassFive')
        main_set.add(Value(comp_hours_class_5, name='compressor_stats_hours_class_5'))

        # heating_rod = features.get_feature('heating.heatingRod.status')
        # heating_rod_on = heating_rod.get_property_value('overall')
        # main_set.add(Value(heating_rod_on, name='heating_rod_active'))

        # heating_rod_on_level1 = heating_rod.get_property_value('level1')
        # main_set.add(Value(heating_rod_on_level1, name='heating_rod_active_level_1'))

        # heating_rod_on_level2 = heating_rod.get_property_value('level2')
        # main_set.add(Value(heating_rod_on_level2, name='heating_rod_active_level_2'))

        # heating_rod_on_level3 = heating_rod.get_property_value('level3')
        # main_set.add(Value(heating_rod_on_level3, name='heating_rod_active_level_3'))

        dhw_charging = features.get_feature('heating.dhw.charging').get_property_value('active')
        main_set.add(Value(dhw_charging, name='hot_water_charging'))

        heating_circulation_pump = features.get_feature('heating.circuits.0.circulation.pump') \
                                       .get_property_value('status') != 'off'
        main_set.add(Value(heating_circulation_pump, name='heating_circulation_pump'))

        dhw_circulation_pump = features.get_feature('heating.dhw.pumps.circulation') \
                                   .get_property_value('status') != 'off'
        main_set.add(Value(dhw_circulation_pump, name='hot_water_circulation_pump'))

        # Pumpe Warmwasserspeicher
        dhw_pump_primary = features.get_feature('heating.dhw.pumps.primary') \
                               .get_property_value('status') != 'off'
        main_set.add(Value(dhw_pump_primary, name='hot_water_primary_pump'))

        # Settings: Hot water target temperature
        hot_water_target = features.get_feature('heating.dhw.temperature.main').get_property_value('value')
        main_set.add(Value(hot_water_target, name='hot_water_target_temp'))

        # Temperature profiles
        program_normal = features.get_feature('heating.circuits.0.operating.programs.normal') \
            .get_property_value('temperature')
        main_set.add(Value(program_normal, name='program_normal_temp'))

        return [main_set, compressor_phase_set]
