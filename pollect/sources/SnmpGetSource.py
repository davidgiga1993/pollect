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
    COUNTER32 = 'Counter32'

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


class MetricDefinition(Log):
    def __init__(self, data: ConfigContainer):
        super().__init__('SnmpMetric')
        self.name = data['name']  # type: str
        self.start = 0  # type: int
        self.end = 0  # type: int
        self.mode = data.get('mode')  # type: Optional[str]
        self.label_name = None  # type: Optional[str]
        self.oid = ''  # type: str

        range_data = data.get('range')  # type: Dict[str, any]
        if range_data is not None:
            self.start = range_data['from']
            self.end = range_data['to']
            self.label_name = range_data['label']
            # We replace the "label_name" in the oid
            self.oid = data.get('oid', ignore_missing_env=self.label_name, required=True)
        else:
            self.oid = data['oid']

        self._last_probe = {}  # type: Dict[str, ProbeValue]
        """
        Holds the timestamps of the last metrics mapped to the metric name.
        This is used to calculate a rate
        """

    def get_label_names(self) -> List[str]:
        """
        Returns the names of the labels used for this metric
        :return: Label names
        """
        if self.label_name is None:
            return []
        return [self.label_name]

    def get_oids(self) -> List[str]:
        """
        Returns all OIDs which should be probed for this metric
        :return: Ids
        """
        if self.label_name is None:
            return [self.oid]

        oids = []
        for x in range(self.start, self.end + 1):
            oids.append(self.oid.replace('${' + self.label_name + '}', str(x)))
        return oids

    def probe(self, snmp_values: Dict[str, SnmpValue]) -> ValueSet:
        data = ValueSet(self.get_label_names())
        if self.label_name is None:
            oid = self.oid
            snmp_value = snmp_values.get(oid)
            if snmp_value is None:
                self.log.error(f'OID {oid} not found')
                return data

            value = self._to_value(snmp_value, oid)
            if value is None:
                return data
            data.values.append(value)
            return data

        # Multi value
        oids = self.get_oids()
        index = 0
        for x in range(self.start, self.end + 1):
            oid = oids[index]
            index += 1
            snmp_value = snmp_values.get(oid)
            if snmp_value is None:
                self.log.error(f'OID {oid} not found')
                return data

            value = self._to_value(snmp_value, oid)
            if value is None:
                continue
            value.label_values = [str(x)]
            data.values.append(value)

        return data

    def _to_value(self, value: SnmpValue, oid: str) -> Optional[Value]:
        """
        Converts the given snmp value to a pollect value
        :param value: Probed value
        """
        if self.mode != 'rate':
            # Regular value
            return Value(value.value, name=self.name)

        last_probe = self._last_probe.get(oid)  # type: Optional[ProbeValue]
        if last_probe is None:
            self._last_probe[oid] = ProbeValue(time.time(), value)
            return None

        # > 1st run - create a rate value for each value and sum them afterwards
        # This is required to handle the overflow of each value correctly
        time_delta = time.time() - last_probe.time
        delta_value = value.get_delta(last_probe.data.value)
        value = Value(delta_value / time_delta, name=self.name)

        # Refresh the data
        last_probe.time = time.time()
        last_probe.data = value
        return value


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
            match = re.match(r'(.+)\s+=\s*(.+?):\s*(\d+)', line)
            if not match:
                continue
            oid = match.group(1)
            values[oid] = SnmpValue(match.group(2), float(match.group(3)))
        return values
