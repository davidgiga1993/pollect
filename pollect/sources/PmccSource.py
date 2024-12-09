import json
import ssl
import threading
from time import sleep
from typing import Optional, List

from websocket import WebSocket, create_connection

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class PmccData:
    soc: int
    """
    Current SOC in %
    """

    start_soc: int
    """
    SOC in % at the beginning of the charging
    """

    ev_charge_rate: float
    """
    Rate in kW
    """

    phasePower: list[float]
    """
    Power measurement of the different phases in W
    """

    def __init__(self):
        self.phasePower = [0, 0, 0]


class PmccSource(Source):
    _connection: Optional[WebSocket]
    _data: PmccData

    def __init__(self, config):
        super().__init__(config)
        self._host = config.get('host')
        self._connection = None
        self._data = PmccData()

    def setup_source(self, global_conf):
        super().setup_source(global_conf)
        threading.Thread(target=self._collect).start()

    def shutdown(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _collect(self):
        while True:
            self._ensure_connected()
            json_str = self._connection.recv()
            data = json.loads(json_str)
            if 'interface' not in data:
                self.log.warning(f'Unexpected message format: {data}')
                continue
            interface = data['interface']
            path = data['path']
            name = data['name']
            args = data.get('args', {})

            if interface == 'de.bebro.WebServer' and name == 'swaggerCurrentSessionChanged' and path == '/':
                args = json.loads(args['swaggerCurrentSession'])
                self._data.start_soc = args['startSoc']
                self._data.soc = args['soc']
                self._data.ev_charge_rate = args['evChargingRatekW']
                continue
            if interface == 'de.bebro.iCAN' and path == '/':
                # Only one of those is set per message
                l1 = args.get('activePowerL1')
                l2 = args.get('activePowerL2')
                l3 = args.get('activePowerL3')
                values = [l1, l2, l3]
                for x in range(len(values)):
                    if values[x] is not None:
                        self._data.phasePower[x] = values[x]
                continue

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        if self._connection is None:
            return None

        soc = ValueSet(labels=['type'])
        soc.add(Value(self._data.soc, name='soc', label_values=['current']))
        soc.add(Value(self._data.start_soc, name='soc', label_values=['start']))

        power = ValueSet(labels=['phase'])
        power.add(Value(self._data.ev_charge_rate, name='chargePower', label_values=['ev']))
        for x in range(len(self._data.phasePower)):
            power.add(Value(self._data.phasePower[x], name='chargePower', label_values=['l' + str(x + 1)]))

        return [power, soc]

    def _ensure_connected(self):
        if self._connection is not None:
            return
        ssl_context = {
            'cert_reqs': ssl.CERT_NONE,
        }
        while True:
            try:
                self._connection = create_connection(f'wss://{self._host}/ws', sslopt=ssl_context)
                return
            except Exception as e:
                self.log.error(f'Could not connect to {self._host}: {e}')
                sleep(5)


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
