import datetime
import os
import re
from functools import cmp_to_key
from typing import List, Dict

from google.cloud import storage
from google.cloud.storage import Blob

from pollect.core.Log import Log
from pollect.libs.google import Helper
from pollect.libs.google.FileProvider import AppVersionFileProvider
from pollect.libs.google.MetricsData import MetaMetric
from pollect.libs.google.StatsParser import StatsParser
from pollect.libs.google.metrics.AppVersionMetrics import AppVersionMetrics
from pollect.libs.google.parser.AppVersionParser import AppVersionParser


class GcsBackend(Log):
    TYPE_SEP = '-'

    def __init__(self, data, apps):
        super().__init__()
        self._bucket_name = data.get('bucketName')
        self._apps = apps
        self._db_dir = data.get('dbDir', 'db')

        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = data.get('keyFile')

        self._last_file = None
        """
        Name of the last file which has been queried
        """

        self._last_modified = None
        """
        Last time the file has been modified
        """

        if not os.path.isdir(self._db_dir):
            os.mkdir(self._db_dir)

        self._crash_metrics = []  # type: List[MetaMetric]

        self.gcs = storage.Client()

        self._create_metrics()

    def download_last_months(self, months: int):
        date = datetime.datetime.now()
        for x in range(months):
            date = Helper.sub_month(date)
            self.download(date)

    def download_latest(self):
        """
        Downloads the latest statistics from GCS
        """
        self.download(datetime.datetime.now())

    def download(self, date: datetime.datetime):
        """
        Download the statistics files for all apps for the given month

        :param date: Month timestamp
        """
        # There is one statistics file per month
        # Therefore we download the correct file once per day
        bucket = self.gcs.get_bucket(self._bucket_name)

        file_names = []
        for metric in self._crash_metrics:
            path = metric.file_provider.get_file(date)
            file_names.append(os.path.basename(path))

        if file_names[0] != self._last_file:
            # A month has passed and a new file must be used
            self._last_file = file_names[0]
            self._last_modified = None

        for file_name in file_names:
            for blob in bucket.list_blobs(prefix='stats/crashes/' + file_name):
                assert isinstance(blob, Blob)
                if self._last_modified is None or self._last_modified != blob.updated:
                    # The file has been changed
                    self.log.info('Downloading stats: ' + file_name)
                    self._last_modified = blob.updated
                    blob.download_to_filename(os.path.join(self._db_dir, file_name))

    def get_latest_crashes(self) -> Dict[str, List[AppVersionMetrics]]:
        """
        Returns the latest crashes for each configured app.
        This works with the cached data - make sure to download them first.

        :return:
        """

        def file_comparator(a, b):
            matcher = re.compile(r'.+_(\d+)_.+')
            first = matcher.match(a)
            second = matcher.match(b)
            if first and second:
                return int(first.group(1)) - int(second.group(1))
            return 0

        self.log.info('Downloading latest crash reports')
        metrics = {}
        for metric in self._crash_metrics:
            files = metric.file_provider.get_all()
            # Find the latest file
            files = sorted(files, key=cmp_to_key(file_comparator))
            if len(files) < 1:
                continue

            # Parse the latest file
            parser = metric.file_provider.create_parser(files[-1])
            parser.parse()
            assert isinstance(parser, AppVersionParser)
            parser.move_to_last_day()

            metrics[metric.export_name] = parser.get_daily_stats()
        return metrics

    def _create_metrics(self):
        """
        Initializes the metric meta data for all defined apps
        """
        self._crash_metrics = []
        for app in self._apps:
            base = StatsParser.CATEGORY_CRASHES + self.TYPE_SEP + app.package + self.TYPE_SEP
            metric = MetaMetric(
                base + StatsParser.FILE_NAME_APP_VERSION,
                'crashes_' + app.package,
                AppVersionFileProvider(self._db_dir, app.package)
            )
            self._crash_metrics.append(metric)
