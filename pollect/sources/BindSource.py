import time
from urllib.error import URLError
from xml.etree import ElementTree

from pollect.core import Helper
from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class BindSource(Source):
    """
    Bind DNS server statistics
    """

    def __init__(self, config):
        super().__init__(config)
        self.url = config.get('url')
        self.views = config.get('views')
        self._last_counters = None
        self._last_time = None

    def _probe(self):
        counter_data = {}

        try:
            xml_data = Helper.get_url(self.url)
        except URLError as e:
            self.log.error('Could not connect to bind statistics: ' + str(e))
            return None

        file = XmlFile(xml_data)
        query_type = file.get_elem('.//counters', {'type': 'qtype'})
        for counter in query_type:
            key = counter.attrib['name'].lower()
            value = int(counter.text)
            counter_data['server.queries|' + key] = value

        data = ValueSet(labels=['queryType'])
        for view_name in self.views:
            low_view_name = view_name.lower()

            view = file.get_elem('.//view', {'name': view_name})
            resolver_stats = file.get_elem('.//counters', {'type': 'resstats'}, view)

            queries = file.get_elem('.//counter', {'name': 'Queryv4'}, resolver_stats)
            counter_data[low_view_name + '.queries|v4'] = int(queries.text)
            queries = file.get_elem('.//counter', {'name': 'Queryv6'}, resolver_stats)
            counter_data[low_view_name + '.queries|v6'] = int(queries.text)

            cache_stats = file.get_elem('.//counters', {'type': 'cachestats'}, view)
            queries = file.get_elem('.//counter', {'name': 'CacheHits'}, cache_stats)
            counter_data[low_view_name + '.cache|hits'] = int(queries.text)
            queries = file.get_elem('.//counter', {'name': 'CacheMisses'}, cache_stats)
            counter_data[low_view_name + '.cache|misses'] = int(queries.text)

            cache = file.get_elem('.//cache', {'name': '_default'}, view)
            for rrset in cache:
                name = file.get_elem('.//name', root=rrset).text.replace('!', '')
                value = file.get_elem('.//counter', root=rrset).text
                data.add(Value(int(value), name=low_view_name + '.cache.rrsets',
                               label_values=[name.lower()]))

        if self._last_time is not None:
            # Calculate delta for counter values
            time_delta = int(time.time() - self._last_time)
            for key, value in counter_data.items():
                name, query_type = key.split('|', 2)
                if key in self._last_counters:
                    data.add(Value((value - self._last_counters[key]) / time_delta,
                                   name=name + '_per_sec',
                                   label_values=[query_type]))

        self._last_time = time.time()
        self._last_counters = counter_data
        return [data]


class XmlFile:
    def __init__(self, data: str):
        self._root = ElementTree.fromstring(data)

    def get_elem(self, name, attribs=None, root=None):
        if attribs is None:
            attribs = {}
        if root is None:
            root = self._root

        elements = root.findall(name)
        for element in elements:
            match = True
            for key, value in attribs.items():
                if element.attrib.get(key) != value:
                    match = False
                    break
            if match:
                return element
