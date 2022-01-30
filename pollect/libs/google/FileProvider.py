import datetime
import os
import re
from abc import abstractmethod
from typing import List

from pollect.libs.google.StatsParser import StatsParser, OverviewParser
from pollect.libs.google.parser.AppVersionParser import AppVersionParser


class FileProvider:
    def __init__(self, db_dir: str, package_name: str):
        self._db_dir = db_dir  # type: str
        self.package_name = package_name  # type: str

    def get_all(self) -> List[str]:
        """
        Returns all files for this package and category

        :return: List of paths
        """

        files = []
        for file in os.listdir(self._db_dir):
            if not re.match(re.escape(self._get_category()) + '_' + re.escape(self.package_name) +
                            r'_[0-9]+_' + re.escape(self._get_suffix()) + r'\.csv', file):
                continue
            files.append(os.path.join(self._db_dir, file))
        return files

    def get_file(self, timestamp: datetime.datetime) -> str:
        """
        Returns the path to the file for the given timestamp

        :param timestamp: Timestamp
        :return: Path to the file
        """

        return os.path.join(self._db_dir,
                            self._get_category() + '_' + self.package_name +
                            '_' + timestamp.strftime(StatsParser.FILE_TIME) + '_' + self._get_suffix() + '.csv')

    @abstractmethod
    def create_parser(self, file: str):
        """
        Creates a new parser for the given file

        :param file: Path to the file
        :return: Parser
        :rtype: StatsParser
        """

    @abstractmethod
    def _get_category(self) -> str:
        pass

    @abstractmethod
    def _get_suffix(self) -> str:
        pass


class OverviewFileProvider(FileProvider):
    def create_parser(self, file: str):
        return OverviewParser(file)

    def _get_category(self) -> str:
        return StatsParser.CATEGORY_CRASHES

    def _get_suffix(self) -> str:
        return 'overview'


class AppVersionFileProvider(FileProvider):
    def create_parser(self, file: str):
        return AppVersionParser(file)

    def _get_category(self) -> str:
        return StatsParser.CATEGORY_CRASHES

    def _get_suffix(self) -> str:
        return 'app_version'
