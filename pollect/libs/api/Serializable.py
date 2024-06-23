from __future__ import annotations

from typing import Dict, List


class Serializeable:
    def __init__(self):
        self._data: Dict[str, any] = {}

    @staticmethod
    def deserialize_from_data(data: Dict[str, any], dto: Serializeable | List[Serializeable]) -> any:
        if isinstance(dto, list):
            if not isinstance(data, list):
                raise ValueError(f'Expected list, but got {data}')

            dto_list = []
            dto_type = type(dto[0])
            for sub in data:
                dto = dto_type()
                dto.deserialize(sub)
                dto_list.append(dto)
            return dto_list

        dto.deserialize(data)
        return dto

    def deserialize(self, data: Dict[str, any]):
        self._data = data
        for key, default_val in self.__dict__.items():
            if key == '_data':
                continue

            if isinstance(default_val, Serializeable):
                default_val.deserialize(data.get(key, {}))
                continue

            self.__dict__[key] = data.get(key, default_val)

    def get_raw(self) -> Dict[str, any]:
        return self._data
