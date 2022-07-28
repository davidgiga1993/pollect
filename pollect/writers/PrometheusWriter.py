from typing import List, Dict

from prometheus_client import start_http_server, Gauge, registry

from pollect.core.ValueSet import ValueSet
from pollect.writers.Writer import Writer


class PromMetric:
    metric: Gauge
    """
    Prometheus metric
    """

    updated: bool
    """
    Indicates if the metric has been updated in the current run
    """

    def __init__(self, metric: Gauge):
        self.metric = metric
        self.updated = True


class PrometheusWriter(Writer):
    _prom_metrics: Dict[str, PromMetric]
    _port: int

    def __init__(self, config):
        super().__init__(config)
        self._port = self.config.get('port', 8080)
        self._prom_metrics = {}

    def supports_partial_write(self) -> bool:
        return True

    def start(self):
        start_http_server(self._port)

    def stop(self):
        pass

    def write(self, data: List[ValueSet]):
        for value in self._prom_metrics.values():
            value.updated = False

        for value_set in data:
            for value_obj in value_set.values:
                path = value_set.name
                if value_obj.name is not None:
                    path += '.' + value_obj.name

                path = path.replace('-', '_').replace('.', '_').replace('!', '')

                if path not in self._prom_metrics:
                    # New metric
                    self._prom_metrics[path] = PromMetric(Gauge(path, path, labelnames=value_set.labels))
                prom_metric = self._prom_metrics[path]
                if len(value_set.labels) > 0:
                    if len(value_obj.label_values) != len(value_set.labels):
                        raise ValueError('Incorrect label count for ' + path + ': Got ' +
                                         str(len(value_set.labels)) + ' labels and ' +
                                         str(len(value_obj.label_values)) + ' label names')

                    prom_metric.metric.labels(*value_obj.label_values).set(value_obj.value)
                    continue
                prom_metric.metric.set(value_obj.value)

        # Check if any metric hasn't been updated, and if so remove it from the prometheus registry
        for key in list(self._prom_metrics.keys()):
            value = self._prom_metrics[key]
            if value.updated:
                continue
            registry.REGISTRY.unregister(value.metric)
            del self._prom_metrics[key]
