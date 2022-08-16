from typing import Optional, List

from pollect.core.ValueSet import ValueSet, Value
from pollect.libs.sma.SmaModbus import SmaModbus, SmaRegisters
from pollect.sources.Source import Source


class SmaPvModbusSource(Source):
    """
    Source for SMA PV inverters (via modbus TCP)
    """

    def __init__(self, config):
        super().__init__(config)
        self._sma = SmaModbus(config['host'], config.get('port', 502))

    def shutdown(self):
        self._sma.close()

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        if not self._sma.is_connected():
            self._sma.connect()
        base_set = ValueSet()
        base_set.add(Value(self._sma.read(SmaRegisters.REG_TEMP).get_as_base_unit(), name='temp'))
        base_set.add(Value(self._sma.read(SmaRegisters.REG_FREQUENCY).get_as_base_unit(), name='frequency'))
        base_set.add(Value(self._sma.read(SmaRegisters.REG_POWER_EFFECTIVE_SUM).get_as_base_unit(), name='power'))
        base_set.add(Value(self._sma.read(SmaRegisters.REG_DC_INPUT_VOLTAGE).get_as_base_unit(), name='dc_voltage'))
        base_set.add(Value(self._sma.read(SmaRegisters.REG_DC_INPUT_CURRENT).get_as_base_unit(), name='dc_current'))

        phase_set = ValueSet(labels=['phase'])
        phase_voltages = [SmaRegisters.REG_VOLTAGE_L1, SmaRegisters.REG_VOLTAGE_L2, SmaRegisters.REG_VOLTAGE_L3]
        for x in range(len(phase_voltages)):
            phase_set.add(Value(self._sma.read(phase_voltages[x]).get_as_base_unit(), name='ac_voltage',
                                label_values=[str(x + 1)]))
        return [base_set, phase_set]
