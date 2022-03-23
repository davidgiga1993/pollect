import time
from typing import Optional

from fritzconnection import FritzConnection

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class FritzSource(Source):
    """
    FritzBox API interaction
    """

    MAX_COUNTER: int = 4294967295  # uint32

    def __init__(self, config):
        super().__init__(config)
        self._pass = config.get('pass')
        self._address = config.get('ip')

        self._last_time = None
        """
        Timestamp of the last run
        
        :type _last_time: float
        """

        self._stats = {}
        """
        Last statistics probed
        
        :type _stats: dict(str, int)
        """

    def _probe(self) -> Optional[ValueSet]:
        connection = FritzConnection(address=self._address, password=self._pass, timeout=10)
        new_data = {}
        service_name = 'WANCommonInterfaceConfig:1'
        if service_name not in connection.services:
            # Use legacy fallback
            service_name = 'WANCommonIFC1'
        output = connection.call_action(service_name, 'GetTotalBytesReceived')
        new_data['recv_bytes_sec'] = output['NewTotalBytesReceived']

        output = connection.call_action(service_name, 'GetTotalBytesSent')
        new_data['sent_bytes_sec'] = output['NewTotalBytesSent']

        data = ValueSet()
        for key, value in new_data.items():
            last_stats = self._stats.get(key)
            self._stats[key] = value
            if last_stats is not None:
                time_delta = int(time.time() - self._last_time)
                value_delta = value - last_stats
                if value_delta < 0:
                    # Overflow happened (previously value was > than current value)
                    value_delta = value + self.MAX_COUNTER

                data.add(Value(value_delta / time_delta, name=key))

        self._last_time = time.time()
        return data
