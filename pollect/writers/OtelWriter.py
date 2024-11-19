from typing import Dict, List, Optional

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics import ObservableGauge
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from pollect.core.ValueSet import ValueSet
from pollect.sources.Source import Source
from pollect.writers.Writer import Writer


class OtelWriter(Writer):

    def __init__(self, config):
        super().__init__(config)
        self._exporter = OTLPMetricExporter()
        self._reader = PeriodicExportingMetricReader(self._exporter)
        self._provider = MeterProvider(metric_readers=[self._reader])
        self._meter = self._provider.get_meter('pollect')
        self._gauges: Dict[str, ObservableGauge] = {}

    def start(self):
        pass

    def stop(self):
        self._reader.shutdown()
        self._exporter.shutdown()

    def write(self, data: List[ValueSet], source_ref: Optional[Source] = None):
        for value_set in data:
            for value_obj in value_set.values:
                gauge = self._get_or_create_gauge(value_set.name)
                attributes = self._get_attributes_from_labels(value_set.labels, value_obj.label_values)
                gauge.set(value_obj.value, attributes=attributes)

    def _get_or_create_gauge(self, name: str) -> ObservableGauge:
        """
        Gets or creates a gauge with the given meter.
        There is no inbuilt way to obtain a gauge from the meter, so we store them in a dictionary
        """
        if name in self._gauges:
            return self._gauges[name]

        gauge = self._meter.create_gauge(name=name)
        self._gauges[name] = gauge
        return gauge

    @staticmethod
    def _get_attributes_from_labels(labels: List[str], label_values: List[str]) -> Dict[str, str]:
        """
        Converts the labels used for prometheus to attributes used for opentelemetry
        """
        attributes = {}
        for i in range(len(labels)):
            attributes[labels[i]] = label_values[i]
        return attributes
