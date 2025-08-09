from pysnmp.hlapi import (SnmpEngine, UsmUserData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity, CommunityData, nextCmd)
from pysnmp.hlapi.auth import (usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol, usmHMAC128SHA224AuthProtocol, usmHMAC192SHA256AuthProtocol, usmHMAC256SHA384AuthProtocol, usmHMAC384SHA512AuthProtocol)
from pysnmp.hlapi.priv import (usmDESPrivProtocol, usm3DESEDEPrivProtocol, usmAesCfb128Protocol, usmAesCfb192Protocol, usmAesBlumenthalCfb256Protocol)
from typing import Dict, List, Optional

from pollect.core.Log import Log
from pollect.core.ValueSet import ValueSet, Value
from pollect.core.config.ConfigContainer import ConfigContainer
from pollect.libs.Utils import chunks
from pollect.sources.Source import Source
from pollect.sources.helper.ProbeValue import ProbeValue


class SnmpValue:
    COUNTER32 = 'counter32'

    __slots__ = ['val_type', 'value']

    def __init__(self, val_type: str, value: float):
        self.val_type = val_type
        self.value = value

    def get_delta(self, old_value: float):
        delta = self.value - old_value
        if self.val_type == self.COUNTER32:
            if delta < 0:
                return (4294967295 - old_value) + self.value + 1
        return delta


class OidLabel:
    def __init__(self, name: str, oid: str):
        self.name = name
        self.oid = oid


class ResolvedOid:
    def __init__(self, oid: str):
        self.oid = oid
        self.label_oids = []  # type: List[str]
        self.static_labels = []  # type: List[str]


class MetricDefinition(Log):
    def __init__(self, data: ConfigContainer):
        super().__init__('SnmpMetric')
        self.name = data['name']  # type: str
        self.mode = data.get('mode')  # type: Optional[str]
        self.label_names = []  # type: List[str]
        """
        The names of all labels
        """

        self.oids = []  # type: List[ResolvedOid]
        """
        OIDs which should be probed
        """

        self._last_probe = {}  # type: Dict[str, ProbeValue]
        """
        Holds the timestamps of the last metrics mapped to the metric name.
        This is used to calculate a rate
        """

        range_data = data.get('range')  # type: Dict[str, any]
        start = 0
        end = 0
        label_name = None
        if range_data is not None:
            start = range_data['from']
            end = range_data['to']
            label_name = range_data['label']
            self.label_names.append(label_name)
            oid = data.get('oid', ignore_missing_env=label_name, required=True)
        else:
            oid = data['oid']

        oid_labels = []  # type: List[OidLabel]
        oid_labels_data = data.get('oidLabels', ConfigContainer({}))  # type: ConfigContainer
        for label_key in oid_labels_data.keys():
            label_oid = oid_labels_data.get(label_key, ignore_missing_env=label_name, required=True)
            oid_labels.append(OidLabel(label_key, label_oid))
            self.label_names.append(label_key)
        self.oids = self._resolve_oids(oid, start, end, label_name, oid_labels)

    def get_oids(self) -> List[str]:
        oids = []
        for resolved in self.oids:
            oids.append(resolved.oid)
            oids.extend(resolved.label_oids)
        return oids

    def probe(self, snmp_values: Dict[str, SnmpValue]) -> ValueSet:
        data = ValueSet(self.label_names)
        for resolved in self.oids:
            snmp_value = snmp_values.get(resolved.oid)
            if snmp_value is None:
                self.log.error(f'OID {resolved.oid} not found')
                continue
            value = self._to_value(snmp_value, resolved.oid)
            if value is None:
                return data
            value.label_values = self._get_label_values(resolved, snmp_values)
            data.values.append(value)
        return data

    def _to_value(self, smnp_value: SnmpValue, oid: str) -> Optional[Value]:
        """
        Converts the given snmp value to a pollect value
        :param smnp_value: Probed value
        """
        if self.mode != 'rate':
            # Regular value
            return Value(smnp_value.value, name=self.name)

        last_probe = self._last_probe.get(oid)  # type: Optional[ProbeValue]
        if last_probe is None:
            self._last_probe[oid] = ProbeValue(time.time(), smnp_value)
            return None
        time_delta = time.time() - last_probe.time
        delta_value = smnp_value.get_delta(last_probe.data.value)
        pollect_value = Value(delta_value / time_delta, name=self.name)
        last_probe.time = time.time()
        last_probe.data = smnp_value
        return pollect_value

    @staticmethod
    def _resolve_oids(oid: str, start: int, end: int, label_name: str, oid_labels: List[OidLabel]) \
            -> List[ResolvedOid]:
        """
        Expands the configuration to the oids which should be probed
        :param oid: Base OID
        :param start: Start index
        :param end: End index
        :param label_name: Name of the iterator label parameter
        :param oid_labels: Labels
        :return: Resolved oids
        """
        if label_name is None:
            resolved = ResolvedOid(oid)
            resolved.label_oids = [x.oid for x in oid_labels]
            return [resolved]
        oids = []
        for x in range(start, end + 1):
            param_str = '${' + label_name + '}'
            resolved = ResolvedOid(oid.replace(param_str, str(x)))
            resolved.static_labels = [str(x)]
            for label in oid_labels:
                resolved.label_oids.append(label.oid.replace(param_str, str(x)))
            oids.append(resolved)
        return oids

    @staticmethod
    def _get_label_values(resolved: ResolvedOid, snmp_values: Dict[str, SnmpValue]) -> List[str]:
        labels = []
        labels.extend(resolved.static_labels)
        for label_oid in resolved.label_oids:
            val = snmp_values.get(label_oid)
            if val is None:
                labels.append('')
                continue
            labels.append(val.value)
        return labels


class SnmpGetSource(Source):
    """
    Using pysnmp to probe SNMP values
    """

    def __init__(self, config: ConfigContainer):
        super().__init__(config)
        self.host = config['host']
        self.metric_defs: List[MetricDefinition] = [MetricDefinition(x) for x in config['metrics']]
        self.oids: List[str] = []
        for metric_def in self.metric_defs:
            self.oids.extend(metric_def.get_oids())
        self.snmp_version = config.get('snmpVersion', 1)
        if self.snmp_version == 3:
            self.username = config.get('username', required=True)
            self.auth_key = config.get('authPassPhrase', required=True)
            self.auth_protocol = config.get('authProtocol', 'SHA')
            self.priv_key = config.get('privacyPassPhrase', required=True)
            self.priv_protocol = config.get('privacyProtocol', 'AES')
        else:
            self.community = config.get('communityString', 'public')

    def _probe(self) -> List[ValueSet]:
        snmp_values = self._get_values(self.oids)
        value_sets = []
        for metric_def in self.metric_defs:
            data = metric_def.probe(snmp_values)
            value_sets.append(data)
        return value_sets

    def _get_values(self, oids: List[str]) -> Dict[str, SnmpValue]:
        if len(oids) > 128:
            values = {}
            for chunk in chunks(oids, 128):
                values.update(self._get_values(chunk))
            return values

        values = {}
        iterator = self._build_iterator(oids)
        for error_indication, error_status, error_index, var_binds in iterator:
            if error_indication:
                raise ValueError(error_indication)
            elif error_status:
                raise ValueError('%s at %s' % (error_status.prettyPrint(), error_index and var_binds[int(error_index) - 1][0] or '?'))
            else:
                for var_bind in var_binds:
                    oid, value = var_bind
                    val_type = type(value).__name__.lower()
                    if val_type == 'octetstring':
                        value = value.prettyPrint()
                    else:
                        value = float(value.prettyPrint())
                    values[str(oid)] = SnmpValue(val_type, value)
        return values

    def _build_iterator(self, oids: List[str]):
        if self.snmp_version == 3:
            return nextCmd(SnmpEngine(),
                           UsmUserData(self.username,
                                       self.auth_key,
                                       self.priv_key,
                                       authProtocol=self._get_auth_protocol(self.auth_protocol),
                                       privProtocol=self._get_priv_protocol(self.priv_protocol)),
                           UdpTransportTarget((self.host, 161)),
                           ContextData(),
                           *[ObjectType(ObjectIdentity(oid)) for oid in oids],
                           lexicographicMode=False)

        return nextCmd(SnmpEngine(),
                       CommunityData(self.community, mpModel=0 if self.snmp_version == 1 else 1),
                       UdpTransportTarget((self.host, 161)),
                       ContextData(),
                       *[ObjectType(ObjectIdentity(oid)) for oid in oids],
                       lexicographicMode=False)

    @staticmethod
    def _get_auth_protocol(protocol: str):
        protocols = {
            'MD5': usmHMACMD5AuthProtocol,
            'SHA': usmHMACSHAAuthProtocol,
            'SHA224': usmHMAC128SHA224AuthProtocol,
            'SHA256': usmHMAC192SHA256AuthProtocol,
            'SHA384': usmHMAC256SHA384AuthProtocol,
            'SHA512': usmHMAC384SHA512AuthProtocol,
        }
        return protocols.get(protocol.upper(), usmHMACSHAAuthProtocol)

    @staticmethod
    def _get_priv_protocol(protocol: str):
        protocols = {
            'DES': usmDESPrivProtocol,
            '3DES': usm3DESEDEPrivProtocol,
            'AES': usmAesCfb128Protocol,
            'AES192': usmAesCfb192Protocol,
            'AES256': usmAesBlumenthalCfb256Protocol,
        }
        return protocols.get(protocol.upper(), usmAesCfb128Protocol)
