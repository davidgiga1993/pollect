from __future__ import annotations

import socket
import struct
import threading
from typing import List, Optional
from pollect.core.Log import Log
from pollect.core.events.Event import Event
from pollect.libs.Units import Unit, Ws, ValueWithUnit


class ObisValueDescription:
    name: str

    phase: Optional[int]

    type: str
    """
    count or avg
    """

    unit: Unit
    """
    Unit of the value
    """

    def __init__(self, name: str, type_str: str, phase: int, unit: Unit):
        self.name = name
        self.type = type_str
        self.phase = phase
        self.unit = unit


class ObisNameMap:
    def __init__(self, obis_base_id: int):
        unit_ws = Ws()
        unit_mv = Unit.milli('V')
        unit_tenth_w = Unit.tenth('W')
        unit_ma = Unit.milli('A')
        unit_mhz = Unit.milli('Hz')
        unit_mcos = Unit.milli('cos φ')

        power = {
            1: 'Wirkleistung_positive',
            2: 'Wirkleistung_negative',
            3: 'Blindleistung_positive',
            4: 'Blindleistung_negative',
            9: 'Scheinleistung_positive',
            10: 'Scheinleistung_negative',
        }
        phase_avg_map = {
            11: ['Strom', unit_ma],
            12: ['Spannung', unit_mv],
            13: ['Leistungsfaktor', unit_mcos],
        }

        obis_base_id = 0
        self._all = {
            self.build_obis(obis_base_id, 13, 4, 0): ObisValueDescription('Leistungsfaktor', 'avg', 0, unit_mcos),
            self.build_obis(obis_base_id, 14, 4, 0): ObisValueDescription('Netzfrequenz', 'avg', 0, unit_mhz),
        }
        phases = [0, 1, 2, 3]
        for phase in phases:
            offset = phase * 20
            for key, value in phase_avg_map.items():
                if phase > 0:
                    self._all[self.build_obis(obis_base_id, key + offset, 4, 0)] = \
                        ObisValueDescription(value[0], 'avg', phase, value[1])

            for key, value in power.items():
                self._all[self.build_obis(obis_base_id, key + offset, 4, 0)] = ObisValueDescription(value, 'avg', phase,
                                                                                               unit_tenth_w)
                self._all[self.build_obis(obis_base_id, key + offset, 8, 0)] = ObisValueDescription(value, 'sum', phase,
                                                                                               unit_ws)

    @staticmethod
    def build_obis(a, b, c, d) -> str:
        return f'{a}:{b}.{c}.{d}'

    def find(self, obis_id: str) -> ObisValueDescription:
        return self._all.get(obis_id)


class ObisValue(ValueWithUnit):
    obis_id: str
    """
    Unique ID of this parameter
    """

    meta: ObisValueDescription

    def __init__(self, obis_id: str, value: int, name_map: ObisNameMap):
        # noinspection PyTypeChecker
        super().__init__(value, None)
        self.obis_id = obis_id
        self._value = value
        self.meta = name_map.find(obis_id)
        if self.meta:
            self.unit = self.meta.unit

    def __str__(self):
        base = super().__str__()
        return f'Phase {self.meta.phase} {self.meta.name} ({self.meta.type}): {base}'


class ByteStream:
    s_int = struct.Struct('!I')
    s_short = struct.Struct('!H')
    s_long = struct.Struct('!Q')

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def pad(self, count: int):
        self._pos += count

    def get_int(self) -> int:
        data = self.s_int.unpack_from(self._data, self._pos)
        self._pos += 4
        return data[0]

    def get_long(self) -> int:
        data = self.s_long.unpack_from(self._data, self._pos)
        self._pos += 8
        return data[0]

    def get_short(self) -> int:
        data = self.s_short.unpack_from(self._data, self._pos)
        self._pos += 2
        return data[0]

    def get(self):
        val = self._data[self._pos]
        self._pos += 1
        return val


class MeterProtocol:
    susyid: str

    serial: str
    """
    Unique device id
    6 byte
    """
    timestamp: int
    """
    4 byte in ms
    """

    obis_pairs: List[ObisValue]
    """
    Values in the datagram
    """

    def __init__(self):
        self.obis_pairs = []


class MeterProtocolParser(Log):
    def __init__(self, obis_base: int):
        super().__init__()
        self._name_map = ObisNameMap(obis_base)

    def parse(self, data: bytes) -> MeterProtocol:
        protocol = MeterProtocol()

        stream = ByteStream(data)
        stream.pad(4)  # SMA\0

        length = stream.get_short()
        if length != 4:
            raise ValueError('Unknown packet')

        tag = stream.get_short()  # Should be tag0 (42), v0
        stream.pad(length)  # Group

        length = stream.get_short()  # Packet length
        tag = stream.get_short()
        if tag != 0x10:
            raise ValueError(f'Unknown SMA Net version {tag}')

        protocol_id = stream.get_short()
        protocol.susyid = stream.get_short()
        protocol.serial = stream.get_int()
        protocol.timestamp = stream.get_int()

        length -= 2 + 2 + 4 + 4
        while length > 4:
            measure_ch = stream.get()
            value_index = stream.get()
            measure_type = stream.get()  # 8=Counter or 4=current average (also length of data value)
            tariff = stream.get()  # 0=sum
            obis = ObisNameMap.build_obis(measure_ch, value_index, measure_type, tariff)
            length -= 4
            if measure_type == 8:
                value = stream.get_long()
                length -= 8
            else:
                value = stream.get_int()
                length -= 4
            value_obj = ObisValue(obis, value, self._name_map)
            if value_obj.meta is None:
                self.log.debug(f'Missing metadata for {obis}')
                continue
            protocol.obis_pairs.append(value_obj)

        return protocol


class SmaEnergyMeter(Log):
    MCAST_GRP: str = '239.12.255.254'
    PORT: int = 9522

    deviceFound: Event
    meterProtocolReceived: Event

    _active: bool = False
    _sock: socket.socket

    def __init__(self, own_ip: str, obis_base: int = 1):
        super().__init__()
        self.deviceFound = Event()
        self.meterProtocolReceived = Event()
        self._parser = MeterProtocolParser(obis_base)
        self._own_ip = own_ip

    def stop(self):
        self._active = False
        self._sock.close()

    def start(self):
        self._active = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass  # Some systems don't support SO_REUSEPORT
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        self._sock.bind((self._own_ip, self.PORT))

        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self._own_ip))
        self._sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                              struct.pack("4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY))

        listen_thr = threading.Thread(target=self._receive, daemon=True)
        listen_thr.start()

    def _receive(self):
        while self._active:
            data, addr = self._sock.recvfrom(1024)
            self._parse(data, addr)

    def send_discovery(self):
        discovery_packet = bytearray.fromhex('53 4d 41 00 00 04 02 a0 ff ff ff ff 00 00 00 20 00 00 00 00')
        while True:
            self._sock.sendto(discovery_packet, (self.MCAST_GRP, self.PORT))

    def _parse(self, data: bytes, addr: any):
        if data.startswith(bytearray.fromhex('534d4100000402A000000001000200000001')):
            self.log.info(f'Found device at {addr}')
            self.deviceFound.fire(addr)
        if len(data) > 600:
            protocol = self._parser.parse(data)
            self.meterProtocolReceived.fire(protocol)
