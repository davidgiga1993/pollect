from typing import List, Dict


class DependencyRequirements:
    """
    Holds all dependencies required by each source
    to provide the user with a good error message in case of missing dependencies,
    as well as additional features such as generating a requirements.txt file
    """
    PSUTIL = 'psutil~=6.1'
    GEVENT = 'gevent~=24.11'

    def __init__(self):
        self.deps: Dict[str, List[str]] = {
            'AppStoreConnectSource': ['appstoreconnect==0.10.0'],
            'CertificateSource': ['pyOpenSSL~=25.0.0'],
            'BindSource': [],
            'DiskUsageSource': [],
            'DummySource': [],
            'EspHomeSource': ['aioesphomeapi~=28.0'],
            'EvccSource': ['websocket_client~=1.8'],
            'FritzSource': ['fritzconnection~=1.14.0'],
            'GdcSource': ['google-cloud-storage~=2.19.0'],
            'HomematicIpSource': ['homematicip~=1.1.6'],
            'HttpIngressSource': [self.GEVENT],
            'HttpSource': [],
            'InterfaceSource': [self.PSUTIL],
            'IOSource': [self.PSUTIL],
            'K8sNamespaceTrafficSource': ['https://github.com/iovisor/bcc/blob/master/INSTALL.md'],
            'MemoryUsageSource': [self.PSUTIL],
            'MMISource': [],
            'OpenhabSource': [],
            'PlexSource': [],
            'PmccSource': ['websocket_client~=1.8'],
            'ProcessSource': [self.PSUTIL],
            'SensorsSource': [],
            'SmaEnergyMeterSource': [],
            'SmaPvModbusSource': ['pymodbus~=3.8.3'],
            'SmartCtlSource': [],
            'SnmpGetSource': [],
            'TcpTimeSource': [],
            'TpLinkEapSource': [],
            'ViessmannSource': [],
            'ZfsSource': [],
            'ZodiacPoolSource': [],

            'MqttWriter': ['paho-mqtt~=2.1.0'],
            'OtelWriter': ['opentelemetry-sdk~=1.29.0', 'opentelemetry-exporter-otlp~=1.29.0'],
            'PrometheusSslWriter': ['prometheus-client~=0.21.1', self.GEVENT],
            'PrometheusWriter': ['prometheus-client~=0.21.1'],
        }
        """
        Source dependencies mapped to their module name
        """

    def get_dependencies_as_text(self, name: str) -> str:
        deps = self.deps.get(name)
        if deps is None:
            return 'Unknown dependency requirements'
        msg = 'The following dependencies are required:\n'
        for package in deps:
            msg += f'- {package}\n'

        return msg
