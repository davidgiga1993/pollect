import threading
from typing import List, Dict, Optional
from wsgiref.simple_server import WSGIServer

from prometheus_client import start_http_server, Gauge, registry, exposition, REGISTRY

from pollect.core.ValueSet import ValueSet
from pollect.libs import Utils
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
    _prom_metrics: Dict[object, Dict[str, PromMetric]]
    """
    Holds all metrics, mapped to their source object and name
    """

    _port: int
    _httpd: Optional[WSGIServer]

    def __init__(self, config):
        super().__init__(config)
        self._port = self.config.get('port', 8080)
        self._prom_metrics = {}

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

    def write(self, data: List[ValueSet], source_ref: object = None):
        existing_metrics = Utils.put_if_absent(self._prom_metrics, source_ref, {})

        for value in existing_metrics.values():
            value.updated = False

        for value_set in data:
            for value_obj in value_set.values:
                path = value_set.name
                if value_obj.name is not None:
                    path += '.' + value_obj.name

                path = path.replace('-', '_').replace('.', '_').replace('!', '')

                if path not in existing_metrics:
                    # New metric
                    existing_metrics[path] = PromMetric(Gauge(path, path, labelnames=value_set.labels))
                prom_metric = existing_metrics[path]
                prom_metric.updated = True
                if len(value_set.labels) > 0:
                    if len(value_obj.label_values) != len(value_set.labels):
                        raise ValueError('Incorrect label count for ' + path + ': Got ' +
                                         str(len(value_set.labels)) + ' labels and ' +
                                         str(len(value_obj.label_values)) + ' label names')

                    prom_metric.metric.labels(*value_obj.label_values).set(value_obj.value)
                    continue
                prom_metric.metric.set(value_obj.value)

        # Check if any metric hasn't been updated, and if so remove it from the prometheus registry
        for key in list(existing_metrics.keys()):
            value = existing_metrics[key]
            if value.updated:
                continue
            registry.REGISTRY.unregister(value.metric)
            del existing_metrics[key]
