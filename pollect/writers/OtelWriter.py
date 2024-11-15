
from typing import List, Optional
from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source
from pollect.writers.Writer import Writer

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics import ObservableGauge


class OtelWriter(Writer):

    def __init__(self, config):
        super().__init__(config)
        self.exporter = OTLPMetricExporter()
        self.reader = PeriodicExportingMetricReader(self.exporter)
        self.provider = MeterProvider(metric_readers=[self.reader])

        self.meter = self.provider.get_meter('pollect')

        self.gauges = {}

    def start(self):
        pass

    def stop(self):
        pass

    def get_metric_name(self, value_set: ValueSet, value_obj: Value):
        """
        Converts the value set and value object to a metric name
        Replaces all invalid characters with underscores
        """
        metric_name = value_set.name
        if value_obj.name is not None:
            metric_name += '.' + value_obj.name
        metric_name = metric_name.replace('-', '_').replace('.', '_').replace('!', '')
        return metric_name

    def get_or_create_gauge(self, name: str):
        """
        Gets or creates a gauge with the given meter.
        There is no inbuilt way to obtain a gauge from the meter, so we store them in a dictionary
        """
        if name in self.gauges.keys():
            return self.gauges[name]
        
        gauge = self.meter.create_gauge(name=name)
        self.gauges[name] = gauge
        return gauge
    
    def get_attributes_from_labels(self, labels: list, label_values: list):
        """
        Converts the labels used for prometheus to attributes used for opentelemetry
        """
        attributes = {}
        for i in range(len(labels)):
            attributes[labels[i]] = label_values[i]
        return attributes

    def write(self, data: List[ValueSet], source_ref: Optional[Source] = None):
        for value_set in data:
            for value_obj in value_set.values:
                metric_name = self.get_metric_name(value_set, value_obj)
                gauge = self.get_or_create_gauge(metric_name)
                attributes = self.get_attributes_from_labels(value_set.labels, value_obj.label_values)
                gauge.set(value_obj.value, attributes=attributes)
