from typing import Optional, List

from pollect.core.ValueCache import ValueCache
from pollect.core.ValueSet import ValueSet, Value
from pollect.libs.sma.SmaEnergyMeter import SmaEnergyMeter, MeterProtocol
from pollect.sources.Source import Source


class SmaEnergyMeterSource(Source):
    """
    Source for SMA energy meters
    """

    def __init__(self, config):
        super().__init__(config)
        self._sma = SmaEnergyMeter(config['hostIp'])
        self._cache = ValueCache()
        self._sma.meterProtocolReceived += self._handle_data

    def _handle_data(self, proto: MeterProtocol):
        self._cache.lock()
        for item in proto.obis_pairs:
            value = Value(item.get_as_base_unit(),
                          name=item.meta.name,
                          label_values=[str(item.meta.phase)])
            if item.meta.type == 'avg':
                self._cache.add(value, average=True)
                continue
            value.name += '_sum'
            self._cache.add(value)
        self._cache.release()

    def setup(self, global_conf):
        self._sma.start()

    def shutdown(self):
        self._sma.stop()

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        value_set = ValueSet(labels=['phase'])
        value_set.values.extend(self._cache.flush_values())
        if len(value_set.values) == 0:
            self.log.warning('No data received from meter')

        for value in value_set.values:
            value.name = value.name.lower().replace(' ', '')

        return value_set
