import re
import subprocess
import time

from pollect.core.ValueSet import ValueSet, Value
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


class SnmpGetSource(Source):
    """
    Wrapper for snmpget
    """

    def __init__(self, config):
        super().__init__(config)
        self.host = config['host']
        self.metrics = config['metrics']
        self.community = config.get('communityString', 'public')
        self._last_probe = {}
        """
        Holds the timestamps of the last metrics mapped to the metric name
        
        :type _last_probe: dict(str, ProbeValue)
        """

    def _probe(self):
        data = ValueSet()
        for metric in self.metrics:
            name = metric['name']
            values = self._probe_metric(metric)

            if metric.get('mode') != 'rate':
                # Regular value - just blindly sum the values
                data.add(Value(sum(value.value for value in values), name=name))
                continue

            last_probe = self._last_probe.get(name)
            if last_probe is None:
                self._last_probe[name] = ProbeValue(time.time(), values)
                continue

            # > 1st run - create a rate value for each value and sum them afterwards
            # This is required to handle the overflow of each value correctly
            time_delta = time.time() - last_probe.time
            delta_sum = 0
            for idx in range(len(values)):
                delta_sum += values[idx].get_delta(last_probe.data[idx].value)
            data.add(Value(delta_sum / time_delta, name=name))

            # Refresh the data
            last_probe.time = time.time()
            last_probe.data = values
        return data

    def _probe_metric(self, metric: dict):
        """
        Probes a single metric. All oids of this metric will be summed

        :param metric: Metric
        :return: Value
        :rtype: List[SnmpValue]
        """
        args = ['snmpget', '-v1', '-c', self.community, self.host]
        args.extend(metric['oids'])
        lines = subprocess.check_output(args).decode('utf-8').splitlines()

        values = []
        for line in lines:
            # Sample lines:
            # iso.3.6.1.2.1.16.1.1.1.1.47 = INTEGER: 47
            # iso.3.6.1.2.1.16.1.1.1.4.43 = Counter32: 27909381
            match = re.match(r'.+\s*=\s*(.+?):\s*([0-9]+)', line)
            if not match:
                continue
            values.append(SnmpValue(match.group(1), float(match.group(2))))
        return values
