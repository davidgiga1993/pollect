import time

from pollect.core import Helper
from pollect.core.ValueSet import ValueSet, Value


class PsutilStats:
    def __init__(self, probe_call, data_map, key_name: str):
        """
        Creates a new psutil statistics collector
        :param probe_call: Call which collects the data from psutil
        :param data_map: Maps the source to the destination parameters.
                         Example: { 'bytes_sent': { 'total: 'total_bytes_sent', 'drv': 'sent_bytes_sec' }}
        :type data_map: dict(str, dict(str, str))
        :param key_name: Name of the value which is used as key by the psutil command (e.g. interfaces, disk, ..)
        """
        self._last_time = None
        """
        Timestamp of the last run
        
        :type __last_time: float
        """

        self._stats = {}
        """
        Last statistics probed
        
        :type _stats: dict(str, int)
        """

        self._probe_call = probe_call
        """
        Function call for probing the data from psutil
        """

        self._data_map = data_map
        self.include = None
        """
        Keys from the probe call which should be included
        
        :type include: None|List[str]
        """
        self.exclude = None
        """
        Keys from the probe call which should be excluded
        
        :type exclude: None|List[str]
        """

        self._key_name = key_name

    def probe(self):
        """
        Probes the data from the probe_call and returns the mapped data

        :return: Mapped data
        :rtype: dict(str, int)
        """
        probe_data = self._probe_call()
        data = ValueSet(labels=[self._key_name])
        for if_name, stats in probe_data.items():
            if not Helper.accept(self.include, self.exclude, if_name):
                continue

            # Convert namedtuple to dict
            stats = stats._asdict()
            if_name = if_name.replace('.', '_')

            last_stats = self._stats.get(if_name)
            self._stats[if_name] = stats

            for source, dest in self._data_map.items():
                if 'total' in dest:
                    total_name = dest['total']
                else:
                    total_name = 'total_' + source

                if 'drv' in dest:
                    derive_name = dest['drv']
                else:
                    derive_name = source + '_sec'

                if total_name is not None:
                    # Total counters might be disabled by setting it to None
                    data.add(Value(stats[source], name=total_name, label_values=[if_name]))

                if last_stats is not None and derive_name is not None:
                    time_delta = int(time.time() - self._last_time)

                    data.add(Value((stats[source] - last_stats[source]) / time_delta, name=derive_name,
                                   label_values=[if_name]))

        self._last_time = time.time()
        return data
