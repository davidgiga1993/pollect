from typing import Optional

from pymodbus.client import ModbusTcpClient
from pymodbus.pdu.register_message import ReadHoldingRegistersResponse

from pollect.core.Log import Log
from pollect.libs.Units import Unit, ValueWithUnit


def u32(hold: ReadHoldingRegistersResponse) -> int:
    return hold.registers[0] << 16 | hold.registers[1]


def u64(hold: ReadHoldingRegistersResponse) -> int:
    return hold.registers[0] << 48 | hold.registers[1] << 32 | hold.registers[2] << 16 | hold.registers[3]


class Register:
    id: int
    unit: Unit
    count: int

    def __init__(self, register: int, unit: Optional[Unit] = None, count: int = 2,
                 decode=u32):
        self.id = register
        self.unit = unit
        self.count = count
        self.decode = decode


class SmaRegisters:
    # See https://my.sma-service.com/servlet/fileField?entityId=ka70X000000bownQAA&field=Attachment_2__Body__s

    _ma = Unit.milli('A')
    _hhz = Unit.hundredth('Hz')
    _hv = Unit.hundredth('V')
    _w = Unit.base('W')
    _wh = Unit.base('Wh')
    _thdc = Unit.tenth('°C')

    REG_DEVICE_TYPE = Register(30051, None)
    REG_STATE = Register(30201, None)

    # Device state
    STATE_ERROR = 35
    STATE_OFF = 303
    STATE_OK = 307
    STATE_WARNING = 455

    # Device types
    ALL_DEVICES = 8000
    DEVICE_SOLAR = 8001
    DEVICE_WING = 8002
    DEVICE_BATTERY = 8007

    REG_DC_INPUT_CURRENT = Register(30769, _ma)  # 0.001A
    REG_DC_INPUT_VOLTAGE = Register(30771, _hv)  # 0.01V

    REG_ENERGY_EFFECTIVE_SUM = Register(30513, _wh, count=4, decode=u64)  # 1Wh
    REG_POWER_EFFECTIVE_SUM = Register(30775, _w)  # 1W

    REG_VOLTAGE_L1 = Register(30783, _hv)  # 0.01V
    REG_VOLTAGE_L2 = Register(30785, _hv)  # 0.01V
    REG_VOLTAGE_L3 = Register(30787, _hv)  # 0.01V
    REG_CURRENT_A_SUM = Register(30795, _ma)  # 0.001A
    REG_FREQUENCY = Register(30803, _hhz)  # 0.01Hz

    REG_TEMP = Register(30953, _thdc)  # 0.1°C


class SmaModbus(Log):
    """
    Communicates via modbus to SMA PV inverter
    """
    _unit_id: int = -1
    _is_connected: bool = False

    def __init__(self, host: str, port: int = 502):
        super().__init__()
        self._client = ModbusTcpClient(host, port=port)

    def is_connected(self) -> bool:
        return self._is_connected

    def connect(self):
        self._client.connect()
        # Ask for unit ID
        reply = self._client.read_holding_registers(42109, count=4, slave=1)
        self._unit_id = reply.registers[3]
        self._is_connected = True

    def close(self):
        self._client.close()
        self._is_connected = False

    def read(self, reg: Register) -> ValueWithUnit:
        value = reg.decode(self._client.read_holding_registers(reg.id, count=reg.count, slave=self._unit_id))
        if value == 0xffffffff or value == 0x80000000:
            # Use 0 as a more sane "not available" value
            value = 0
        return ValueWithUnit(value, reg.unit)
