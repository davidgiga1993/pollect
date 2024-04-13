import asyncio
from threading import Thread
from typing import Optional, List, Dict

import aioesphomeapi

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class Sensor:
    def __init__(self, name: str, sensor_type: str):
        self.name = name
        self.sensor_type = sensor_type


class EspHomeSource(Source):
    _values: ValueSet
    _loop: asyncio.AbstractEventLoop

    def __init__(self, config):
        super().__init__(config)
        self._values = ValueSet(['name'])

        hostname = config['host']
        port = config.get('port', 6053)
        psk = config['psk']
        self._api = aioesphomeapi.APIClient(hostname, port, password='', noise_psk=psk)

    def setup(self, global_conf):
        super().setup(global_conf)
        self._loop = asyncio.new_event_loop()
        t = Thread(target=self._start_background_loop, args=(self._loop,), daemon=True)
        t.start()
        asyncio.run_coroutine_threadsafe(self._connect(), self._loop)

    def shutdown(self):
        super().shutdown()

        asyncio.run_coroutine_threadsafe(self._api.disconnect(), self._loop)
        self._loop.stop()

    async def _connect(self):
        await self._api.connect(login=True)
        sensors, entities = await self._api.list_entities_services()
        sensor_by_keys: Dict[int, Sensor] = dict(
            (sensor.key, Sensor(sensor.name, sensor.device_class)) for sensor in sensors)

        def on_event(state):
            if isinstance(state, aioesphomeapi.SensorState):
                sensor = sensor_by_keys[state.key]
                sensor_value = state.state
                for value in self._values.values:
                    if value.label_values[0] == sensor.name:
                        value.value = sensor_value
                        return

                self._values.add(Value(sensor_value, [sensor.name],
                                       name=sensor.sensor_type))

        self._api.subscribe_states(on_event)

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        return self._values

    @staticmethod
    def _start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()
