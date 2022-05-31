import re
import subprocess
import time
from typing import Dict, List, Optional

from pollect.core.Log import Log

from pollect.core.ValueSet import ValueSet, Value
from pollect.core.config.ConfigContainer import ConfigContainer
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
                # Value did overflow - get the delta between the overflow and the last number
                # and add the new value and +1 since there is one increment from max val to 0
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
        """
        OIDs of the dynamic labels
        """

        self.static_labels = []  # type: List[str]
        """
        Values of static labels
        """


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

            # We replace the "label_name" in the oid
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
        """
        Returns all OIDs which should be probed
        :return: OIDs
        """
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

        # > 1st run - create a rate value for each value and sum them afterwards
        # This is required to handle the overflow of each value correctly
        time_delta = time.time() - last_probe.time
        delta_value = smnp_value.get_delta(last_probe.data.value)
        pollect_value = Value(delta_value / time_delta, name=self.name)

        # Refresh the data
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
        """
        Returns the values of the dynamic oid labels
        :return: Label values
        """
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
    Wrapper for snmpget
    """

    def __init__(self, config):
        super().__init__(config)
        self.host = config['host']
        self.metric_defs = [MetricDefinition(x) for x in config['metrics']]  # type: List[MetricDefinition]
        self.oids = []  # type: List[str]
        for metric_def in self.metric_defs:
            self.oids.extend(metric_def.get_oids())

        self.community = config.get('communityString', 'public')

    def _probe(self) -> List[ValueSet]:
        snmp_values = self._get_values(self.oids)

        value_sets = []
        for metric_def in self.metric_defs:
            data = metric_def.probe(snmp_values)
            value_sets.append(data)
        return value_sets

    def _get_values(self, oids: List[str]) -> Dict[str, SnmpValue]:
        """
        Probes a list of oids

        :param oids: List of oids which should be probed
        :return: Values
        """
        args = ['snmpget', '-v1', '-c', self.community, self.host]
        args.extend(oids)
        lines = subprocess.check_output(args).decode('utf-8').splitlines()

        values = {}
        for line in lines:
            # Sample lines:
            # iso.3.6.1.2.1.16.1.1.1.1.47 = INTEGER: 47
            # iso.3.6.1.2.1.16.1.1.1.4.43 = Counter32: 27909381
            # iso.3.6.1.2.1.16.1.1.1.4.43 = STRING: "sample value"
            match = re.match(r'(.+)\s+=\s*(.+?):\s*(.+)', line)
            if not match:
                continue
            oid = match.group(1)
            val_type = match.group(2).lower()
            if val_type == 'string':
                value = match.group(3)[1:-1]  # Remove "" wrapping
            else:
                value = float(match.group(3))
            values[oid] = SnmpValue(val_type, value)
        return values
