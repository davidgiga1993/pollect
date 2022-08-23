import json
import logging
import threading
from typing import Optional, List, Dict

from gevent import pywsgi

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class MetricDefinition:
    labels: List[str]
    name: str
    type: str

    def __init__(self, name: str, data: Dict[str, any]):
        self.name = name
        self.type = data.get('type', 'gauge')
        self.labels = data.get('labels', [])

    def is_counter(self) -> bool:
        return self.type == 'counter'


class HttpIngressSource(Source):
    _port: int
    _server: Optional[pywsgi.WSGIServer] = None
    _metrics_definitions: Dict[str, MetricDefinition]
    _metrics: Dict[str, ValueSet]

    def __init__(self, config):
        super().__init__(config)
        self._port = config['port']
        metrics_definitions = [MetricDefinition(name, metric_def)
                               for name, metric_def in config['metrics'].items()]
        self._metrics = {}
        self._metrics_definitions = {}
        for metric_def in metrics_definitions:
            self._metrics_definitions[metric_def.name] = metric_def

            value_set = ValueSet(labels=metric_def.labels)
            value_set.name = metric_def.name
            self._metrics[metric_def.name] = value_set

    def setup(self, global_conf):
        super().setup(global_conf)
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        def start():
            self._server = pywsgi.WSGIServer(('0.0.0.0', self._port), self._serve, log=logger)
            self._server.serve_forever()

        launcher = threading.Thread(target=start)
        launcher.start()

    def shutdown(self):
        if self._server:
            self._server.stop()
            self._server = None

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        return list(self._metrics.values())

    def _update_metrics(self, data: Dict[str, any]):
        metrics = data['metrics']
        for name, data in metrics.items():
            metric_def = self._get_metric_def(name)
            labels = data.get('labels', {})
            value = data.get('value', 0)
            value_set = self._get_metric(name)

            if metric_def.is_counter() and len(value_set.values) > 0:
                # Increment the previous value
                value += value_set.values[0].value

            self._get_metric(name).values.clear()
            value_set.add(Value(value, label_values=self._map_labels(value_set, labels)))

    def _get_metric_def(self, name: str) -> MetricDefinition:
        metric_def = self._metrics_definitions.get(name)
        if metric_def is None:
            raise ValueError(f'Metric def {name} not found')
        return metric_def

    def _get_metric(self, name: str) -> ValueSet:
        metrics = self._metrics.get(name)
        if metrics is None:
            raise ValueError(f'Metric {name} not found')
        return metrics

    def _serve(self, env, start_response):
        """
        Handles incoming requests.
        :param env: WSGI env
        :param start_response: Callback
        :return: Body
        """
        method = env['REQUEST_METHOD']
        if method == 'POST':
            content_type = env.get('CONTENT_TYPE', '')
            # Payload shall be any type of json ("text/json" or "application/json", ..)
            if '/json' not in content_type:
                return self._reply(start_response, {'error': 'content-type must be json'}, code=400)

            # Very crude input parsing, the request path is ignored
            payload = env['wsgi.input'].read()
            encoding = 'utf-8'  # Only support utf-8 - good enough for now
            str_payload = payload.decode(encoding)  # type: str
            try:
                data = json.loads(str_payload)
                self._update_metrics(data)
                return self._reply(start_response, {'status': 'metrics updated'})
            except ValueError as e:
                return self._reply(start_response, {'error': str(e)}, code=400)

        return self._reply(start_response, {'status': 'alive'})

    @staticmethod
    def _reply(start_response, param: Dict[str, any], code: int = 200):
        """
        Sends the given json object back

        :param start_response: WSGI callback
        :param param: Dictionary to be serialized
        :param code: Http status code, might be 200 or 400
        :return: Body payload
        """
        headers = [('Content-Type', 'text/json')]
        if code == 400:
            start_response('400 Bad Request', headers)
        else:
            start_response('200 OK', headers)
        return [json.dumps(param).encode('utf-8')]

    @staticmethod
    def _map_labels(value_set: ValueSet, labels: Dict[str, str]) -> List[str]:
        label_values = []
        for name in value_set.labels:
            if name not in labels:
                raise ValueError(f'Missing label: {name}')
            label_values.append(labels[name])
        return label_values
