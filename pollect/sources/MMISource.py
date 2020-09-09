import json

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source

from audiapi.API import API
from audiapi.model.VehicleDataResponse import VehicleDataResponse
from audiapi.Services import LogonService, CarService, VehicleStatusReportService


class MMISource(Source):
    def __init__(self, config):
        super().__init__(config)
        self.vin = config.get('vin')
        self.cred_file = config.get('credentials')

    def _probe(self):
        api = API()
        logon_service = LogonService(api)
        if not logon_service.restore_token():
            # We need to login
            with open(self.cred_file) as data_file:
                login_data = json.load(data_file)
            logon_service.login(login_data['user'], login_data['pass'])

        car_service = CarService(api)
        vehicles_response = car_service.get_vehicles()
        data = ValueSet()
        for vehicle in vehicles_response.vehicles:
            if self.vin != vehicle.vin:
                continue

            status_report_service = VehicleStatusReportService(api, vehicle)
            report = status_report_service.get_stored_vehicle_data()
            assert isinstance(report, VehicleDataResponse)
            for field in report.data_fields:
                if field.name == 'UTC_TIME_AND_KILOMETER_STATUS':
                    data.add(Value(int(field.value), name='kilometers'))  # int in km
                    continue
                if field.name == 'TEMPERATURE_OUTSIDE':
                    data.add(Value(int(int(field.value) / 10 - 273), name='temp.outsite'))
                    continue
                if field.name == 'TOTAL_RANGE':
                    data.add(Value(int(field.value), name='range.total'))  # int in km
                    continue
                if field.name == 'TANK_LEVEL_IN_PERCENTAGE':
                    data.add(Value(int(field.value), name='tankLevel'))  # int in %
                    continue
                if field.name == 'OIL_LEVEL_DIPSTICKS_PERCENTAGE':
                    data.add(Value(float(field.value), name='oilLevelPercent'))  # in %
                    continue
                if field.name == 'ADBLUE_RANGE':
                    data.add(Value(int(field.value), name='range.adblue'))  # int in km
                    continue

            return data

        print('VIN not found')
        return None
