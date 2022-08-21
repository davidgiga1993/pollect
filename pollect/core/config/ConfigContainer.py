import os
import re
from typing import Dict, Optional


class ConfigContainer:
    """
    Holds a configuration dict and resolves values via the environment
    """

    # Matches ${SOME-131asd}
    pattern = re.compile(r'\${([A-Z0-9a-z_-]+?)}')

    def __init__(self, data: Dict[str, any]):
        self._data = data

    def __getitem__(self, item):
        return self.get(item, required=True)

    def keys(self):
        return self._data.keys()

    def values(self):
        for value in self._data.values():
            yield self._resolve(value)

    def items(self):
        return self._data.items()

    def get(self, key: str, default: any = None, required: bool = False,
            ignore_missing_env: Optional[str] = None) -> Optional[any]:
        if key not in self._data:
            if required:
                raise KeyError(f'{key} not found')
            return default

        value = self._data[key]
        return self._resolve(value, key, ignore_missing_env)

    def _resolve(self, value: any, key: str = None, ignore_missing_env: Optional[str] = None):
        """
        Resolves any environment references in the given value
        :param value: Value
        :return: Resolved value
        """
        if isinstance(value, dict):
            return ConfigContainer(value)
        if isinstance(value, list):
            # Special handling for lists:
            # if the list contains objects, we need to wrap those with the config container as well
            for idx in range(len(value)):
                if isinstance(value[idx], dict):
                    value[idx] = ConfigContainer(value[idx])

        if not isinstance(value, str):
            return value

        # Handle $ escaping
        value = value.replace('$$', '$')
        for env_key in self.pattern.findall(value):
            env_value = os.environ.get(env_key)
            if env_value is None:
                if env_key == ignore_missing_env:
                    continue
                raise KeyError(f'Environment {env_key} not found, defined in {key}')
            value = value.replace('${' + env_key + '}', env_value)

        return value
