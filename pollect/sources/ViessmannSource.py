"""
Collects data from viessmann devices.
This requires a viessmann account
"""
from __future__ import annotations

import os
from typing import Optional, List

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source
from pollect.viessmann.ViessmannApi import ViessmannApi, OAuthToken


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
            self.api.use_token(token)

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:

        # A token refresh might be required
        token = self.api.get_token()
        self.api.use_token(token)
        if token.access_token != self.api.get_token().access_token:
            # Token has changed
            token.persist(self.AUTH_FILE)

        main_set = ValueSet()
        installations = self.api.get_installations()
        install_id = installations[0].get_id()
        gateway = installations[0].get_gateway()
        gateway_serial = gateway.get_property('serial')
        device_id = 0

        features = self.api.get_features(install_id, gateway_serial, device_id)

        # Rücklauf (hydraulische weiche)
        return_temp = features.get_entity('heating.sensors.temperature.return').get_property_value('value')
        main_set.add(Value(return_temp, name='return_temperature'))

        # Außentemperatur
        outside_temp = features.get_entity('heating.sensors.temperature.outside').get_property_value('value')
        main_set.add(Value(outside_temp, name='outside_temperature'))

        hot_water_storage_top = features.get_entity('heating.dhw.sensors.temperature.hotWaterStorage.top') \
            .get_property_value('value')
        main_set.add(Value(hot_water_storage_top, name='hot_water_storage_top'))

        hot_water_storage = features.get_entity('heating.dhw.sensors.temperature.hotWaterStorage') \
            .get_property_value('value')
        main_set.add(Value(hot_water_storage, name='hot_water_storage'))

        # Vorlauf
        supply_temp = features.get_entity('heating.circuits.0.sensors.temperature.supply').get_property_value('value')
        main_set.add(Value(supply_temp, name='supply_temp'))

        secondary_temp_return = features.get_entity('heating.secondaryCircuit.sensors.temperature.return') \
            .get_property_value('value')
        main_set.add(Value(secondary_temp_return, name='secondary_return_temp'))

        secondary_temp_supply = features.get_entity('heating.secondaryCircuit.sensors.temperature.supply') \
            .get_property_value('value')
        main_set.add(Value(secondary_temp_supply, name='secondary_supply_temp'))

        compressor_active = features.get_entity('heating.compressors.0').get_property_value('active')
        main_set.add(Value(compressor_active, name='compressor_active'))

        compressor_phase = features.get_entity('heating.compressors.0').get_property_value('phase')
        main_set.add(Value(compressor_phase != 'off', name='compressor_phase'))

        compressor_kwh_power = features.get_entity('heating.compressors.0.power').get_property_value('value')
        main_set.add(Value(compressor_kwh_power, name='compressor_power'))

        compressor_stats = features.get_entity('heating.compressors.0.statistics')
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

        heating_rod = features.get_entity('heating.heatingRod.status')
        heating_rod_on = heating_rod.get_property_value('overall')
        main_set.add(Value(heating_rod_on, name='heating_rod_active'))

        heating_rod_on_level1 = heating_rod.get_property_value('level1')
        main_set.add(Value(heating_rod_on_level1, name='heating_rod_active_level_1'))

        heating_rod_on_level2 = heating_rod.get_property_value('level2')
        main_set.add(Value(heating_rod_on_level2, name='heating_rod_active_level_2'))

        heating_rod_on_level3 = heating_rod.get_property_value('level3')
        main_set.add(Value(heating_rod_on_level3, name='heating_rod_active_level_3'))

        dhw_charging = features.get_entity('heating.dhw.charging').get_property_value('active')
        main_set.add(Value(dhw_charging, name='hot_water_charging'))

        heating_circulation_pump = features.get_entity('heating.circuits.0.circulation.pump') \
                                       .get_property_value('status') == 'on'
        main_set.add(Value(heating_circulation_pump, name='heating_circulation_pump'))

        dhw_circulation_pump = features.get_entity('heating.dhw.pumps.circulation') \
                                   .get_property_value('status') == 'on'
        main_set.add(Value(dhw_circulation_pump, name='hot_water_circulation_pump'))

        # Pumpe Warmwasserspeicher
        dhw_pump_primary = features.get_entity('heating.dhw.pumps.primary') \
                               .get_property_value('status') == 'on'
        main_set.add(Value(dhw_pump_primary, name='hot_water_primary_pump'))

        # Settings: Hot water target temperature
        hot_water_target = features.get_entity('heating.dhw.temperature').get_property_value('value')
        main_set.add(Value(hot_water_target, name='hot_water_target_temp'))

        # Temperature profiles
        program_normal = features.get_entity('heating.circuits.0.operating.programs.normal')\
            .get_property_value('temperature')
        main_set.add(Value(program_normal, name='program_normal_temp'))

        return main_set
