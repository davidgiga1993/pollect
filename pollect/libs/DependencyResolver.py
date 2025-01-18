from typing import Set

from pollect.Requirements import DependencyRequirements
from pollect.core.Core import Configuration


class DependencyResolver:
    def __init__(self, config: Configuration):
        self._config = config

    def print(self):
        """
        Prints all required dependencies
        """
        sources = self._config.get_all_sources()
        writers = self._config.get_all_writers()

        requirements = DependencyRequirements()

        deps: Set[str] = set([])
        for data in sources:
            src_name = data['type'] + 'Source'
            packages = requirements.deps.get(src_name, [])
            deps.update(packages)

        for data in writers:
            src_name = data['type'] + 'Writer'
            packages = requirements.deps.get(src_name, [])
            deps.update(packages)

        pip_packages = [d for d in deps if not d.startswith('http')]
        pip_packages.sort()
        for package in pip_packages:
            print(package)
