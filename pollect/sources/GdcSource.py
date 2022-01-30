from datetime import datetime, timedelta

from pollect.core.ValueSet import ValueSet, Value
from pollect.libs.google.AppConfig import AppConfig
from pollect.libs.google.GcsBackend import GcsBackend
from pollect.sources.Source import Source


class GdcSource(Source):
    """
    Collects google play statistics such as crash and ANR rates
    The data is fetched from GCS and stored locally

    Requires google-cloud-storage
    """

    def __init__(self, config):
        super().__init__(config)
        apps = []
        for app in config.get('apps', []):
            apps.append(AppConfig(app))

        self._gcs = GcsBackend(config, apps)

    def _probe(self):
        self._gcs.download_latest()
        apps = self._gcs.get_latest_crashes()

        data = ValueSet()
        data.labels = ['versionCode', 'type']

        # The API has ~1 day latency - if no data has been found for > 3 days we assume there were no crashes
        # since google does not add new entries to the csv if there are no crashes
        date_threshold = datetime.today() - timedelta(days=3)
        latest_data = 0
        for name, crashes in apps.items():
            for crash in crashes:
                if crash.date < date_threshold:
                    crash.crashes = 0
                    crash.anrs = 0
                if crash.date.timestamp() > latest_data:
                    latest_data = crash.date.timestamp()

                data.add(Value(crash.crashes, label_values=[str(crash.app_version), 'crash'], name=name))
                data.add(Value(crash.anrs, label_values=[str(crash.app_version), 'anr'], name=name))

        meta_data = ValueSet()
        meta_data.add(Value(int(latest_data), name='latestUpdate'))
        return [data, meta_data]
