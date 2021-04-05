from typing import List

from prometheus_client import start_http_server, Gauge

from pollect.core.ValueSet import ValueSet
from pollect.writers.Writer import Writer


class PrometheusWriter(Writer):
    def __init__(self, config):
        super().__init__(config)
        self._init = False
        self._port = self.config.get('port', 8080)
        self._exporters = {}

    def start(self):
        start_http_server(self._port)

    def stop(self):
        pass

    def write(self, data: List[ValueSet]):
        for value_set in data:
            for value_obj in value_set.values:
                path = value_set.name
                if value_obj.name is not None:
                    path += '.' + value_obj.name

                path = path.replace('-', '_').replace('.', '_').replace('!', '')

                if path not in self._exporters:
                    self._exporters[path] = Gauge(path, path, labelnames=value_set.labels)
                gauge = self._exporters[path]
                if len(value_set.labels) > 0:
                    if len(value_obj.label_values) != len(value_set.labels):
                        raise ValueError('Incorrect label count for ' + path + ': Got ' +
                                         str(len(value_set.labels)) + ' labels and ' +
                                         str(len(value_obj.label_values)) + ' label names')

                    gauge.labels(*value_obj.label_values).set(value_obj.value)
                    continue
                gauge.set(value_obj.value)
