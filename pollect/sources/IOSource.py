import psutil

from pollect.core import Helper
from pollect.sources.Source import Source
from pollect.sources.helper.PsutilStats import PsutilStats


class IOSource(Source):
    def __init__(self, config):
        super().__init__(config)
        self._stats = PsutilStats(self._probe_call, {
            'read_count': {'total': None, 'drv': 'reads_sec'},
            'write_count': {'total': None, 'drv': 'writes_sec'},
            'read_bytes': {'total': None},
            'write_bytes': {'total': None},
        }, 'disk')

        self._stats.include = Helper.remove_empty_list(config.get('include'))
        self._stats.exclude = Helper.remove_empty_list(config.get('exclude'))

    @staticmethod
    def _probe_call():
        return psutil.disk_io_counters(perdisk=True)

    def _probe(self):
        return self._stats.probe()
