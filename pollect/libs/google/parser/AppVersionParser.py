from typing import List

from pollect.libs.google.StatsParser import OverviewParser, StatsParser
from pollect.libs.google.metrics.AppVersionMetrics import AppVersionMetrics


class AppVersionParser(OverviewParser):

    def get(self, field_name: str):
        if field_name == StatsParser.FILE_NAME_APP_VERSION:
            return self.get_version_code()
        return super().get(field_name)

    def get_daily_stats(self) -> List[AppVersionMetrics]:
        """
        Returns the stats for the day at the cursor position for all app versions
        :return: List of version stats
        """
        stats = []
        date = self.get_date()
        while date == self.get_date():
            stats.append(AppVersionMetrics(date, self.get_version_code(),
                                           self.get_daily_crashes(), self.get_daily_anrs()))
            if not self.next():
                break
        return stats

    def get_version_code(self):
        return int(self._current_row[2])

    def get_daily_crashes(self):
        return int(self._current_row[3])

    def get_daily_anrs(self):
        return int(self._current_row[4])
