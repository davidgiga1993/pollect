from abc import abstractmethod
from datetime import datetime


class StatsParser:
    FILE_TIME = '%Y%m'

    CATEGORY_CRASHES = 'crashes'

    FIELD_DAILY_ANRS = 'daily_anrs'
    FIELD_DAILY_CRASHES = 'daily_crashes'

    FILE_NAME_APP_VERSION = 'app_version'

    def __init__(self, category: str, file: str):
        self.category = category
        """
        The category this file belongs to
        
        :type category: str
        """

        self.file = file
        self._line_idx = None
        self._current_row = None
        self._lines = []

    def parse(self):
        with open(self.file, encoding='utf-16-le') as file:
            self._lines = file.readlines()

        # Start with the actual data (row 1)
        self._line_idx = 0
        self.next()

    @abstractmethod
    def get(self, field_name):
        """
        Returns the given field from current row

        :param field_name: Name of the field
        :return: Field value
        """
        pass

    def get_date(self):
        """
        Returns the date

        :return: Datetime
        :rtype: datetime
        """
        return datetime.strptime(self._current_row[0], '%Y-%m-%d')

    def move_to_day(self, end_day: int):
        """
        Moves to the given day of the month

        :param end_day: Day of the month
        :return: True if the day could be reached, false if the end of file was reached
        :rtype: bool
        """
        while self.get_date().day < end_day:
            if not self.next():
                # EoF
                return False
        return True

    def move_to_last_day(self):
        """
        Moves the cursor to the first row of the last day in the file
        """
        self._line_idx = len(self._lines) - 2
        self.next()
        last_day = self.get_date()
        # Now find the start of the last day
        self._line_idx = 0
        self.move_to_day(last_day.day)

    def next(self):
        """
        Moves the cursor to the next line

        :return: True if a new line is available, false otherwise
        :rtype: bool
        """
        self._line_idx += 1
        if self._line_idx < len(self._lines):
            self._current_row = self._lines[self._line_idx].split(',')
            return True
        return False


class OverviewParser(StatsParser):

    def __init__(self, file: str):
        super().__init__(StatsParser.CATEGORY_CRASHES, file)

    def get(self, field_name):
        if field_name == StatsParser.FIELD_DAILY_ANRS:
            return self.get_daily_anrs()
        if field_name == StatsParser.FIELD_DAILY_CRASHES:
            return self.get_daily_crashes()
        return None

    def get_daily_crashes(self):
        return int(self._current_row[2])

    def get_daily_anrs(self):
        return int(self._current_row[3])
