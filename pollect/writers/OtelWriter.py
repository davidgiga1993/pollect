
from typing import Dict, List, Optional
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
    
    def get_attributes_from_labels(self, labels: List[str], label_values: List[str]) -> Dict[str, str]:
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
                gauge = self.get_or_create_gauge(value_set.name)
                attributes = self.get_attributes_from_labels(value_set.labels, value_obj.label_values)
                gauge.set(value_obj.value, attributes=attributes)
