import psutil

from pollect.core import Helper
from pollect.sources.Source import Source
from pollect.sources.helper.PsutilStats import PsutilStats


class InterfaceSource(Source):
    def __init__(self, config):
        super().__init__(config)
        data_mapping = {
            'bytes_sent': {'total': None, 'drv': 'sent_bytes_sec'},
            'packets_sent': {'total': None, 'drv': 'sent_packets_sec'},
            'bytes_recv': {'total': None, 'drv': 'recv_bytes_sec'},
            'packets_recv': {'total': None, 'drv': 'recv_packets_sec'},
        }

        if config.get('includeTotal', False):
            for key, value in data_mapping.items():
                value['total'] = 'total_' + key

        self._stats = PsutilStats(self._probe_call, data_mapping, 'interface')
        self._stats.include = Helper.remove_empty_list(config.get('include'))
        self._stats.exclude = Helper.remove_empty_list(config.get('exclude'))

    @staticmethod
    def _probe_call():
        return psutil.net_io_counters(pernic=True)

    def _probe(self):
        return self._stats.probe()
