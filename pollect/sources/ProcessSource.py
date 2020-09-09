import re

import psutil

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class ProcessSource(Source):
    """
    Collects data about a process
    """

    def __init__(self, config):
        super().__init__(config)
        self.proc_regex = config.get('procRegex')
        self.memory = config.get('memory', True)
        self.load = config.get('load', True)

    def _probe(self):
        data = ValueSet(labels=['pidx'])
        matches = 0
        for proc in psutil.process_iter():
            if not self._matches(proc):
                continue

            self._collect(matches, proc, data)
            matches += 1
        data.add(Value(matches, label_values=['all'], name='process_count'))
        return data

    def _matches(self, process: psutil.Process):
        try:
            cmd_lines = process.cmdline()
            return re.search(self.proc_regex, ' '.join(cmd_lines)) is not None
        except psutil.AccessDenied:
            return False

    def _collect(self, index: int, process: psutil.Process, data: ValueSet):
        if self.load:
            data.add(Value(process.cpu_percent(), label_values=[str(index)], name='load_percent'))
        if self.memory:
            data.add(Value(process.memory_info().vms, label_values=[str(index)], name='virtual_memory'))
        return data
