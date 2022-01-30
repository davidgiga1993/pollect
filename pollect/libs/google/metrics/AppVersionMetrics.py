import datetime


class AppVersionMetrics:
    def __init__(self, date: datetime.datetime, app_version: int, crashes: int, anrs: int):
        self.date = date
        self.app_version = app_version
        self.crashes = crashes
        self.anrs = anrs
