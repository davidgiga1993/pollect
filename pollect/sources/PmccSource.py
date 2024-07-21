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
        errors = ValueSet(labels=['code'])

        soc = self._get('/v1/api/SCC/properties/StateOfCharge')
        general.add(Value(soc, name='state_of_charge'))

        charge_type = self._get('/v1/api/SCC/properties/propChargeType')
        general.add(Value(charge_type, name='charge_type'))

        cpu_temp = self._get('/v1/api/SelfTest/Temp_CPU/properties')['temperature']
        temperature.add(Value(cpu_temp, name='temp', label_values=['cpu']))

        free_memory = self._get('/v1/api/SelfTest/RAM/properties')['ramFree']
        general.add(Value(free_memory, name='free_memory'))

        emcc = self._get('/v1/api/SelfTest/EMMC/properties')
        general.add(Value(emcc['PersistencyFreeSpace'], name='free_space_persistent_storage'))
        general.add(Value(emcc['SystemFreeSpace'], name='free_space_system_storage'))

        canbus = self._get('/v1/api/iCAN/properties')
        general.add(Value(canbus['propM4TempLCD'], name='temp_lcd'))

        temp_data = json.loads(canbus['propjIcanTempChanged'])
        temperature.add(Value(temp_data['Internal_Micro'], name='temp', label_values=['uc']))
        temperature.add(Value(temp_data['Internal_Relay'], name='temp', label_values=['relay1']))
        temperature.add(Value(temp_data['Internal_Relay_2'], name='temp', label_values=['relay2']))

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
            errors.add(Value(value, name='errors', label_values=[key]))
        return [general, temperature, errors]

    def _get(self, path: str, nested_json: bool = False) -> Dict[str, any]:
        return self._exec("GET", path, nested_json)

    def _put(self, path: str, nested_json: bool = False) -> Dict[str, any]:
        return self._exec("PUT", path, nested_json)

    def _exec(self, method: str, path: str, nested_json: bool = False, depth: int = 0) -> Dict[str, any]:
        reply = self._s.request(method, self._url + path, verify=False, headers={
            'Referer': self._url,
        })
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


if __name__ == '__main__':
    PmccSource({'type': '', 'password': 'NiXrBbIP', 'url': 'https://iccpd-0123207.home.local'}).probe()

"""
All endpoints
  ["^/$"] = { "GET" },
    ["^/swagger.json$"] = { "GET" },
    ["^/swaggerui/bower/swagger.?ui/dist/.*"] = { "GET" },
    ["^/HMI/properties/disclaimerText$"] = {"GET"},
    ["^/HMI/properties/dozeMode$"] = {"GET"},
    ["^/HMI/properties/swUpdateProgress$"] = {"GET"},
    ["^/HMI/properties/propHmiUserUnlocked$"] = {"GET"},
    ["^/HMI/properties/deviceProtection$"] = {"GET"},
    ["^/HMI/properties/pukRemainingWaitTime$"] = {"GET"},
    ["^/HMI/properties/pinRemainingWaitTime$"] = {"GET"},
    ["^/HMI/properties/propHmiPinMaxAttempts$"] = {"GET"},
    ["^/HMI/properties/propHmiPukMaxAttempts$"] = {"GET"},
    ["^/HMI/properties/propHmiPinUnlockAttempts$"] = {"GET"},
    ["^/HMI/properties/propHmiPukUnlockAttempts$"] = {"GET"},
    ["^/HMI/properties/guestPinEnabled$"] = {"PUT"},
    ["^/HMI/properties/currentSessionBusinessTrip$"] = {"GET"},
    ["^/HMI/properties/displayBrightness$"] = {"GET"},
    ["^/HMI/properties/currentLanguage$"] = {"GET"},
    ["^/HMI/properties/languageList$"] = {"GET"},
    ["^/HMI/properties/currentCountry$"] = {"GET"},
    ["^/HMI/properties/countryList$"] = {"GET"},
    ["^/HMI/properties/timeZoneId$"] = {"GET"},
    ["^/HMI/properties/batteryStatusUnitDistance$"] = {"GET","PUT"},
    ["^/HMI/properties/chargeRateUnitPower$"] = {"GET","PUT"},
    ["^/HMI/properties/chargeTimeOptionFinish$"] = {"GET","PUT"},
    ["^/HMI/properties/onboardingDone$"] = {"GET"},
    ["^/HMI/properties/selectedDistanceUnit$"] = {"GET","PUT"},
    ["^/HMI/properties/selectedTemperatureUnit$"] = {"GET","PUT"},
    ["^/HMI/properties/currentFAHMessage$"] = {"GET"},
    ["^/HMI/properties/hmiState$"] = {"GET"},
    ["^/HMI/methods/touch$"] = {"PUT"},
    ["^/HMI/methods/screenshot$"] = {"GET"},
    ["^/HMI/methods/translatedDisclaimerText$"] = {"PUT"},
     ["^/HMI/methods/setAdminPin$"] = {"PUT"},
    ["^/HMI/methods/setGuestPin$"] = {"PUT"},
    ["^/HMI/methods/disableGuestPin$"] = {"PUT"},
    ["^/HMI/methods/setDeviceProtection$"] = {"PUT"},
    ["^/HMI/methods/verifyPin$"] = {"PUT"},
    ["^/HMI/methods/verifyPuk$"] = {"PUT"},
    ["^/HMI/methods/showTestPicture$"] = {"PUT"},
    ["^/HMI/methods/hideTestPicture$"] = {"PUT"},
    ["^/HMI/methods/setDisplayBrightness$"] = {"PUT"},
    ["^/HMI/methods/setCurrentLanguageByIso$"] = {"PUT"},
    ["^/HMI/methods/setCurrentCountryByIso$"] = {"PUT"},
    ["^/HMI/methods/setCurrentTimeZoneId$"] = {"PUT"},
    ["^/HMI/methods/setOnboardingDone$"] = {"PUT"},
    ["^/HMI/methods/setStopWaveAnimation$"] = {"PUT"},
    ["^/ConnectionManager/NetworkStatus/properties/global_connection_state$"] = {"GET"},
    ["^/ConnectionManager/NetworkController/properties/last_wifi_scan_results$"] = {"GET"},
    ["^/ConnectionManager/NetworkController/properties/wifi_mac_address$"] = {"GET"},
    ["^/ConnectionManager/NetworkController/properties/plc_mac_address$"] = {"GET"},
    ["^/ConnectionManager/NetworkController/methods/scan_once$"] = {"PUT"},
    ["^/ConnectionManager/NetworkController/methods/plc_pushbutton_join$"] = {"PUT"},
    ["^/ConnectionManager/NetworkController/methods/plc_pushbutton_leave$"] = {"PUT"},
    ["^/HEMS_Mgr/CoordiatedCharging/properties/coordinatedChargingAvailable$"] = {"GET"},
    ["^/HEMS_Mgr/CoordiatedCharging/properties/json_tariffPowerValues$"] = {"GET"},
    ["^/HEMS_Mgr/CoordiatedCharging/properties/json_tariffPriceTable$"] = {"GET"},
    ["^/DTCHandler/methods/PurgeDTCs$"] = {"PUT"},
    ["^/DTCHandler/methods/GetDTC$"] = {"PUT"},
    ["^/DTCHandler/methods/GetDTCV2G$"] = {"PUT"},
    ["^/DTCHandler/methods/GetDTCs$"] = {"PUT"},
    ["^/DTCHandler/methods/GetDTCsV2G$"] = {"PUT"},
    ["^/ConnectionManager/methods/connect_to_ap$"] = {"PUT"},
    ["^/ConnectionManager/methods/connect_to_ap_with_id$"] = {"PUT"},
    ["^/ConnectionManager/methods/reconnect$"] = {"PUT"},
    ["^/ConnectionManager/methods/disconnect_from_ap$"] = {"PUT"},
    ["^/ConnectionManager/methods/connect_to_plc$"] = {"PUT"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_connection_state$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_connected_profile$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_ap_id$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/ap_mode_ip_address$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_ssid$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_security_type$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_signal_strength$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_ip_address$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_gateway$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_netmask$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_ipv6_address$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_ipv6_gateway$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_ipv6_prefixlength$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/wifi_nameservers$"] = {"GET"},
     ["^/ConnectionManager/NetworkStatus/properties/last_wifi_status$"] = {"GET"},
    ["^/iCAN/properties/propIcanDetectStateCarCable$"] = {"GET"},
    ["^/iCAN/properties/propIcanDetectStateGridCable$"] = {"GET"},
    ["^/iCAN/properties/propIcanPhaseDetectedL1$"] = {"GET"},
    ["^/iCAN/properties/propIcanPhaseDetectedL2$"] = {"GET"},
    ["^/iCAN/properties/propIcanPhaseDetectedL3$"] = {"GET"},
    ["^/iCAN/properties/propIcanDeratingReason$"] = {"GET"},
    ["^/iCAN/properties/propIcanStateGroundMoni$"] = {"GET"},
    ["^/iCAN/properties/propIcanStatePEGrid$"] = {"GET"},
    ["^/iCAN/properties/propIcanGridCableR1Value$"] = {"GET"},
    ["^/iCAN/properties/propIcanGridCableR2Value$"] = {"GET"},
    ["^/iCAN/properties/propIcanCarCableRcValue$"] = {"GET"},
    ["^/iCAN/properties/propIcanStateSystem$"] = {"GET"},
    ["^/iCAN/properties/propjIcanCurrentLimit$"] = {"GET"},
    ["^/iCAN/properties/propjIcanEnergy$"] = {"GET"},
    ["^/iCAN/properties/propjIcanTempChanged$"] = {"GET"},
    ["^/iCAN/properties/propjIcanPwrIdentHW$"] = {"GET"},
    ["^/iCAN/properties/propjIcanKomIdentHW$"] = {"GET"},
    ["^/iCAN/properties/propjIcanPwrIdentSW$"] = {"GET"},
    ["^/iCAN/properties/propjIcanKomIdentSW$"] = {"GET"},
    ["^/iCAN/properties/propjIcanCable$"] = {"GET"},
    ["^/iCAN/properties/propEepromVersion$"] = {"GET"},
    ["^/iCAN/properties/propEepComSerialNumber$"] = {"GET"},
    ["^/iCAN/properties/propEepPowerSerialNumber$"] = {"GET"},
    ["^/iCAN/properties/propEepSysSerialNumber$"] = {"GET"},
    ["^/iCAN/properties/propEepSysTimestamp$"] = {"GET"},
    ["^/iCAN/properties/propEepPowerTimestamp$"] = {"GET"},
    ["^/iCAN/properties/propEepComTimestamp$"] = {"GET"},
    ["^/iCAN/properties/propEepSystemPartNumber$"] = {"GET"},
    ["^/iCAN/properties/propEepSystemBrandID$"] = {"GET"},
    ["^/iCAN/properties/propjEepLedHalfRingTable$"] = {"GET"},
    ["^/iCAN/properties/propjEepLedPwrButtonTable$"] = {"GET"},
    ["^/iCAN/properties/propEepSysHostName$"] = {"GET"},
    ["^/iCAN/properties/propEepHlcGlobalEnabled$"] = {"GET","PUT"},
    ["^/iCAN/properties/propEepHlcPncTls$"] = {"GET","PUT"},
    ["^/iCAN/properties/propEepSysFazitIdentification$"] = {"GET"},
    ["^/iCAN/properties/propEepSysPartNumber$"] = {"GET"},
    ["^/iCAN/properties/propEepSysEcuHardwareNumber$"] = {"GET"},
    ["^/iCAN/properties/propEepSysEcuHardwareVersionNumber$"] = {"GET"},
    ["^/iCAN/properties/propM4TempT1$"] = {"GET"},
    ["^/iCAN/properties/propM4TempT2$"] = {"GET"},
    ["^/iCAN/properties/propM4TempLCD$"] = {"GET"},
    ["^/iCAN/properties/propM4SysTicks$"] = {"GET"},
    ["^/iCAN/properties/propM4SwVersion$"] = {"GET"},
    ["^/iCAN/properties/propM4IcanDbcProtVersion$"] = {"GET"},
    ["^/iCAN/properties/propM4CoreState$"] = {"GET"},
    ["^/iCAN/properties/propIcanIsInitialized$"] = {"GET"},
    ["^/iCAN/properties/propjLedState$"] = {"GET"},
    ["^/iCAN/properties/localLatestVersion$"] = {"GET"},
    ["^/iCAN/properties/oemSWVersion$"] = {"GET"},
    ["^/iCAN/methods/methICanActivateGroundMonitor$"] = {"PUT"},
    ["^/SCC/properties/Connection$"] = {"GET"},
    ["^/SCC/properties/ActiveSession$"] = {"GET"},
    ["^/SCC/properties/ChargeState$"] = {"GET"},
    ["^/SCC/properties/StateOfCharge$"] = {"GET"},
    ["^/SCC/properties/AutoUpdate$"] = {"GET","PUT"},
    ["^/SCC/properties/json_ConnectedCarDetails$"] = {"GET"},
    ["^/SCC/properties/json_GroupWhitelistEV$"] = {"GET"},
    ["^/SCC/properties/json_IndividualWhitelistEV$"] = {"GET"},
    ["^/SCC/properties/json_ACEnergySingleDemand$"] = {"GET"},
    ["^/SCC/properties/propVasAvailable$"] = {"GET"},
    ["^/SCC/properties/json_carMinMaxPwm$"] = {"GET"},
    ["^/SCC/properties/propSeccIsInitialized$"] = {"GET"},
    ["^/SCC/properties/json_ACPowerPlan$"] = {"GET"},
    ["^/SCC/properties/PEID$"] = {"GET"},
    ["^/SCC/properties/propCurrentTariffPrice$"] = {"GET"},
    ["^/SCC/properties/propAuthorizationType$"] = {"GET"},
    ["^/SCC/properties/json_powerLimitReason$"] = {"GET"},
    ["^/SCC/properties/propCarMacAddress$"] = {"GET"},
    ["^/SCC/properties/propClockSource$"] = {"GET"},
    ["^/SCC/properties/propTariffDataSource$"] = {"GET"},
     ["^/SCC/properties/propCurrentTariff$"] = {"GET"},
    ["^/SCC/properties/propQCALinkState$"] = {"GET"},
    ["^/SCC/properties/isDeepSleepDisabled$"] = {"GET","PUT"},
    ["^/SCC/properties/propSysHwCurrentLimit$"] = {"GET"},
    ["^/SCC/properties/propMinimumCurrentLimit$"] = {"GET"},
    ["^/SCC/properties/propAutoDimmingAllow$"] = {"PUT","GET"},
    ["^/SCC/properties/propBacklightLevel$"] = {"GET","PUT"},
    ["^/SCC/properties/json_CurrentCableInformation$"] = {"GET"},
    ["^/SCC/properties/json_knownCableLimits$"] = {"GET"},
    ["^/SCC/properties/propHMICurrentLimit$"] = {"GET","PUT"},
    ["^/SCC/properties/propCurrentUserSetTime$"] = {"GET","PUT"},
    ["^/SCC/properties/propCurrentTime$"] = {"GET"},
    ["^/SCC/properties/propTimeSource$"] = {"GET"},
    ["^/SCC/properties/propChargeType$"] = {"GET"},
    ["^/SCC/properties/propChargeSessionTimeCharged$"] = {"GET"},
    ["^/SCC/properties/propConsolidatedMaxCurrentLimit$"] = {"GET"},
    ["^/SCC/properties/propPowerStatusEVUpdated$"] = {"GET"},
    ["^/SCC/properties/propTargetSOC$"] = {"GET"},
    ["^/SCC/properties/propStartSOC$"] = {"GET"},
    ["^/SCC/properties/propChargeDuration$"] = {"GET"},
    ["^/SCC/properties/propCummulativeChargeDuration$"] = {"GET"},
    ["^/SCC/properties/propPlugDuration$"] = {"GET"},
    ["^/SCC/properties/propChargeParamEV$"] = {"GET"},
    ["^/SCC/properties/propIsV2GPLCEnabled$"] = {"GET"},
    ["^/SCC/properties/propSECCPibFileInfo$"] = {"GET"},
    ["^/SCC/properties/propSessionEnergy$"] = {"GET"},
    ["^/SCC/methods/sendDefaultTariff$"] = {"PUT"},
    ["^/SCC/methods/methGetQCALinkStatus$"] = {"PUT"},
    ["^/SCC/methods/methSetQCAPibFile$"] = {"PUT"},
    ["^/SCC/methods/methSetIsV2GPLCEnabled$"] = {"PUT"},
    ["^/SCC/methods/methAddJSONGroupPolicy$"] = {"PUT"},
    ["^/SCC/methods/methAddGroupPolicy$"] = {"PUT"},
    ["^/SCC/methods/methRemoveGroupWhiteListentry$"] = {"PUT"},
    ["^/SCC/methods/methRemoveIndividualWhiteListEntry$"] = {"PUT"},
    ["^/SCC/methods/methAddUserNameToIndividualWhiteListEntry$"] = {"PUT"},
    ["^/SCC/methods/methIsEntryInIndividualList$"] = {"PUT"},
    ["^/SCC/methods/methAddCurrentCarToWhiteList$"] = {"PUT"},
    ["^/SCC/methods/methStartSimulationMode$"] = {"PUT"},
    ["^/SCC/methods/methStopSimulationMode$"] = {"PUT"},
    ["^/SCC/methods/methDisableDeepSleepTimed$"] = {"PUT"},
    ["^/SCC/methods/methEnableDisableVAS$"] = {"PUT"},
    ["^/SCC/methods/methExportGroupWhiteList$"] = {"GET"},
    ["^/SCC/methods/methImportGroupWhiteList$"] = {"PUT"},
    ["^/HEMS_Mgr/ShipController/properties/json_connectedDevice$"] = {"GET"},
    ["^/HEMS_Mgr/ShipController/properties/ownSKI$"] = {"GET"},
    ["^/HEMS_Mgr/ShipController/properties/json_foundServicesList$"] = {"GET"},
     ["^/HEMS_Mgr/ShipController/methods/connectTo$"] = {"PUT"},
    ["^/HEMS_Mgr/ShipController/methods/removeDeviceFromTrustStore$"] = {"PUT"},
    ["^/HEMS_Mgr/ShipController/methods/clearTrustStore$"] = {"PUT"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_connection_state$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_number_networks$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_number_stations$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_rx_datarate$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_tx_datarate$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_dak$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_security_id$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_ip_address$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_gateway$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_netmask$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_ipv6_address$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_ipv6_gateway$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_ipv6_prefixlength$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_nameservers$"] = {"GET"},
    ["^/ConnectionManager/NetworkStatus/properties/plc_search_domains$"] = {"GET"},
    ["^/ConnectionManager/Config/properties/all_profiles_info$"] = {"GET"},
    ["^/ConnectionManager/Config/properties/profile_names$"] = {"GET"},
    ["^/ConnectionManager/Config/properties/profile_count$"] = {"GET"},
    ["^/ConnectionManager/Config/methods/add_profile$"] = {"PUT"},
    ["^/ConnectionManager/Config/methods/delete_profile$"] = {"PUT"},
    ["^/ConnectionManager/Config/methods/get_profile$"] = {"PUT"},
    ["^/ConnectionManager/Config/methods/update_profile$"] = {"PUT"},
    ["^/PMNG/properties/encryptedContents$"] = {"GET"},
    ["^/PMNG/properties/defaultConfig$"] = {"PUT","GET"},
    ["^/PMNG/properties/demoModeEnable$"] = {"GET","PUT"},
    ["^/PMNG/methods/factoryReset$"] = {"PUT"},
    ["^/PMNG/methods/dumpContents$"] = {"PUT"},
    ["^/PMNG/methods/fillContents$"] = {"PUT"},
    ["^/PMNG/methods/encryptContents$"] = {"PUT"},
    ["^/SelfTest/EMMC/properties/SystemFreeSpace$"] = {"GET"},
    ["^/SelfTest/EMMC/properties/PersistencyFreeSpace$"] = {"GET"},
    ["^/ConnectionManager/Config/properties/ap_settings$"] = {"GET"},
    ["^/ConnectionManager/Config/properties/wifi_mode$"] = {"GET"},
    ["^/ConnectionManager/Config/properties/is_background_scanning_enabled$"] = {"GET"},
    ["^/ConnectionManager/Config/properties/is_plc_enabled$"] = {"GET"},
    ["^/ConnectionManager/Config/methods/set_wifi_mode$"] = {"PUT"},
       ["^/ConnectionManager/Config/methods/set_ap_settings$"] = {"PUT"},
    ["^/ConnectionManager/Config/methods/set_is_plc_enabled$"] = {"PUT"},
    ["^/SelfTest/RAM/properties/ramFree$"] = {"GET"},
    ["^/SelfTest/Temp_CPU/properties/temperature$"] = {"GET"},
    ["^/HEMS_Mgr/properties/version$"] = {"GET"},
    ["^/HEMS_Mgr/properties/json_useCaseInfo$"] = {"GET"},
    ["^/HEMS_Mgr/methods/startStopSimulationMode$"] = {"PUT"},
    ["^/thermomanagement/properties/currentReduction$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/thresholdTemperatureRelay1$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/deratingFactorRelay1$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/samplingIntervalRelay1$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/thresholdTemperatureRelay2$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/deratingFactorRelay2$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/samplingIntervalRelay2$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/thresholdTemperatureInfraCable$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/deratingFactorInfraCable$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/samplingIntervalInfraCable$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/thresholdTemperatureCpu$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/deratingFactorCpu$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/samplingIntervalCpu$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/thresholdTemperatureLed$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/deratingFactorLed$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/samplingIntervalLed$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/thresholdTemperatureMCU$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/deratingFactorMCU$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/samplingIntervalMCU$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/thresholdTemperatureLCD$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/deratingFactorLCD$"] = {"GET","PUT"},
    ["^/thermomanagement/properties/samplingIntervalLCD$"] = {"GET","PUT"},
    ["^/WebServer/properties/swaggerStatus$"] = {"GET"},
    ["^/WebServer/properties/swaggerHistory$"] = {"GET"},
    ["^/WebServer/properties/swaggerPowerCurve$"] = {"GET"},
    ["^/WebServer/properties/swaggerPowerPlan$"] = {"GET"},
    ["^/WebServer/properties/swaggerCurrentSession$"] = {"GET"},
    ["^/WebServer/properties/updateState$"] = {"GET"},
    ["^/WebServer/properties/updateOnline$"] = {"GET"},
    ["^/WebServer/properties/downloadProgress$"] = {"GET"},
    ["^/WebServer/properties/pairingLoginState$"] = {"GET"},
    ["^/WebServer/properties/pairedUserList$"] = {"GET"},
    ["^/WebServer/properties/cumulativeChargingDetails$"] = {"GET"},
    ["^/WebServer/properties/chargingTariff$"] = {"GET"},
    ["^/WebServer/properties/csrData$"] = {"GET"},
    ["^/WebServer/properties/storeClientCertificate$"] = {"PUT","GET"},
    ["^/WebServer/properties/storeV2GServerCertificate$"] = {"PUT","GET"},
    ["^/WebServer/properties/chargeState$"] = {"GET"},
    ["^/WebServer/properties/powerCurveMeasurementTimeInterval$"] = {"GET","PUT"},
    ["^/WebServer/properties/powerCurveUploadTimeInterval$"] = {"GET","PUT"},
     ["^/WebServer/properties/mbbError$"] = {"GET"},
    ["^/WebServer/properties/verificationUri$"] = {"GET"},
    ["^/WebServer/methods/modifyWebPasswordForUser$"] = {"PUT"},
    ["^/WebServer/methods/modifyWebPasswordForTechnician$"] = {"PUT"},
    ["^/WebServer/methods/startUpdate$"] = {"PUT"},
    ["^/WebServer/methods/checkVersion$"] = {"PUT"},
    ["^/WebServer/methods/startDownload$"] = {"PUT"},
    ["^/WebServer/methods/pairing$"] = {"PUT"},
    ["^/WebServer/methods/deletePairedUser$"] = {"PUT"},
    ["^/WebServer/methods/StartStopChargeStatisticsUpload$"] = {"PUT"},
    ["^/WebServer/methods/downloadChargingTariff$"] = {"PUT"},
    ["^/WebServer/methods/generateCSR$"] = {"PUT"},
    ["^/WebServer/methods/generateV2GCSR$"] = {"PUT"},
    ["^/WebServer/methods/generateEEBusCertificate$"] = {"PUT"},
    ["^/WebServer/methods/updateBackendCertificate$"] = {"PUT"},
    ["^/WebServer/methods/updateV2GCertificate$"] = {"PUT"},
    ["^/WebServer/methods/triggerDiagnosticUpload$"] = {"PUT"},
    ["^/ConnectionManager/Config/properties/all_plc_profiles$"] = {"GET"},
    ["^/ConnectionManager/Config/methods/update_plc_profile$"] = {"PUT"},
    ["^/ConnectionManager/Config/methods/delete_plc_profile$"] = {"PUT"},
    ["^/update$"] = {"GET","PUT","POST"}
"""
