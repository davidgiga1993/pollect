import logging
import threading
from urllib.parse import parse_qs

from gevent import pywsgi
from prometheus_client import exposition
from prometheus_client import registry

from pollect.writers.PrometheusWriter import PrometheusWriter


class PrometheusSslWriter(PrometheusWriter):
    def __init__(self, config):
        super().__init__(config)
        self._server = None
        self._key = config['key']
        self._cert = config['cert']

        # See if the files exist
        with open(self._key):
            pass
        with open(self._cert):
            pass

    def start(self):
        def serve(env, start_response):
            params = parse_qs(env['QUERY_STRING'])
            accept_header = env['HTTP_ACCEPT']

            reg = registry.REGISTRY
            encoder, content_type = exposition.choose_encoder(accept_header)
            if 'name[]' in params:
                reg = reg.restricted_registry(params['name[]'])
            output = encoder(reg)
            headers = [('Content-Type', content_type)]

            start_response('200 OK', headers)
            return [output]

        logger = logging.getLogger('prom')
        logger.setLevel(logging.ERROR)

        def start():
            self._server = pywsgi.WSGIServer(('127.0.0.1', self._port), serve,
                                             keyfile=self._key, certfile=self._cert,
                                             log=logger)
            self._server.start()

        launcher = threading.Thread(target=start)
        launcher.start()

    def stop(self):
        self._server.stop()
