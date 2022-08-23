from __future__ import annotations
import threading
from typing import List, Dict, Optional
from wsgiref.simple_server import WSGIServer

from prometheus_client import Gauge, registry, exposition, REGISTRY

from pollect.core.ValueSet import ValueSet, Value
from pollect.libs import Utils
from pollect.sources.Source import Source
from pollect.writers.Writer import Writer


class PromMetric:
    """
    Represents a single metric
    """

    metric: Gauge
    """
    Prometheus metric
    """

    updated: Dict[str, bool]
    """
    Indicates if the metric with the given label values has been updated in the current run
    """

    def __init__(self, metric: Gauge):
        self.metric = metric
        self.updated = {}

    def reset_state(self):
        for key in self.updated.keys():
            self.updated[key] = False

    def update(self, value_set: ValueSet, value_obj: Value):
        if len(value_set.labels) > 0:
            if len(value_obj.label_values) != len(value_set.labels):
                raise ValueError('Incorrect label count for ' + str(value_obj) + ': Got ' +
                                 str(len(value_set.labels)) + ' labels and ' +
                                 str(len(value_obj.label_values)) + ' label names')

            self.metric.labels(*value_obj.label_values).set(value_obj.value)
            label_key = '\t'.join(value_obj.label_values)
            self.updated[label_key] = True
            return

        self.metric.set(value_obj.value)
        self.updated[''] = True

    def remove_not_updated(self, cache: MetricsCache):
        for key in list(self.updated.keys()):
            if self.updated[key] is True:
                continue
            del self.updated[key]

            if key == '':
                # In case we don't have any labels
                # we can just unregister the metric, since no other
                # source is using it
                # (Since > 1 sources using the same metric name will cause issues anyways)
                cache.unregister(self)
                continue
            labels = key.split('\t')
            self.metric.remove(*labels)


class MetricsCache:
    """
    Holds the prometheus metrics objects
    as well as all exported metrics so we can check
    if a metric was removed
    """
    _source_metrics: Dict[object, Dict[str, PromMetric]]
    """
    Maps a source object to the metrics created by that object 
    """

    _prom_counter: Dict[str, Gauge]

    def __init__(self):
        self._source_metrics = {}
        self._prom_counter = {}

    def get_or_create(self, path: str, label_names: List[str]) -> Gauge:
        """
        Returns an existing gauge or creates a new one if it doesn't exist
        :param path: Path
        :param label_names: Label anmes
        :return:  Gauge
        """
        gauge = self._prom_counter.get(path)
        if gauge is None:
            gauge = Gauge(path, path, labelnames=label_names)
            self._prom_counter[path] = gauge
            return gauge
        return gauge

    def clear(self):
        """
        Removes all metrics
        """
        for value in self._prom_counter.values():
            registry.REGISTRY.unregister(value)
        self._source_metrics.clear()
        self._prom_counter.clear()

    def unregister(self, metric: PromMetric):
        """
        Removes the given metric
        :param metric: Metric to be removed
        """
        registry.REGISTRY.unregister(metric.metric)
        for key, value in self._prom_counter.items():
            if value == metric.metric:
                del self._prom_counter[key]
                break
        for metrics in self._source_metrics.values():
            for key, value in metrics.items():
                if value == metric:
                    del metrics[key]
                    return

    def get_metrics(self, source_ref) -> Dict[str, PromMetric]:
        return Utils.put_if_absent(self._source_metrics, source_ref, {})


class PrometheusWriter(Writer):
    _port: int
    _httpd: Optional[WSGIServer]
    _cache: MetricsCache

    def __init__(self, config):
        super().__init__(config)
        self._port = self.config.get('port', 8080)
        self._cache = MetricsCache()

    def supports_partial_write(self) -> bool:
        return True

    def start(self):
        """
        Starts the prometheus exporter.
        We start the server manually, so we can also terminate it
        """
        """Starts a WSGI server for prometheus metrics as a daemon thread."""
        addr: str = '0.0.0.0'
        port = self._port

        class TmpServer(exposition.ThreadingWSGIServer):
            """Copy of ThreadingWSGIServer to update address_family locally"""

        TmpServer.address_family, addr = exposition._get_best_family(addr, port)
        app = exposition.make_wsgi_app(REGISTRY)
        self._httpd = exposition.make_server(addr, port, app, TmpServer, handler_class=exposition._SilentHandler)
        t = threading.Thread(target=self._httpd.serve_forever)
        t.daemon = True
        t.start()

    def stop(self):
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd = None

    def clear(self):
        """
        Removes all metrics
        """
        self._cache.clear()

    def write(self, data: List[ValueSet], source_ref: Optional[Source] = None):
        # Get the previous metrics for the given source
        existing_metrics = self._cache.get_metrics(source_ref)

        for value in existing_metrics.values():
            value.reset_state()

        for value_set in data:
            for value_obj in value_set.values:
                path = value_set.name
                if value_obj.name is not None:
                    path += '.' + value_obj.name

                path = path.replace('-', '_').replace('.', '_').replace('!', '')

                if path not in existing_metrics:
                    # New metric for the current source
                    gauge = self._cache.get_or_create(path, label_names=value_set.labels)
                    existing_metrics[path] = PromMetric(gauge)

                prom_metric = existing_metrics[path]
                prom_metric.update(value_set, value_obj)

        for value in list(existing_metrics.values()):
            value.remove_not_updated(self._cache)
