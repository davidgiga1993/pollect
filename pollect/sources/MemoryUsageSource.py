import psutil

from pollect.core import OSEnv
from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class MemoryUsageSource(Source):
    def _probe(self):
        memory = psutil.virtual_memory()

        data = ValueSet(labels=['type'])
        data.add(Value(memory.total, label_values=['total']))
        data.add(Value(memory.available, label_values=['available']))
        data.add(Value(memory.used, label_values=['used']))

        if OSEnv.is_linux():
            data.add(Value(memory.cached, label_values=['cached']))
        return data
