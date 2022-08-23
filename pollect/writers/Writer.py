from abc import abstractmethod
from typing import List, Optional

from pollect.core.Log import Log
from pollect.core.ValueSet import ValueSet
from pollect.sources.Source import Source


class Writer(Log):
    """
    General writer
    """

    def __init__(self, config):
        super().__init__()
        self.config = config

    def supports_partial_write(self) -> bool:
        """
        Indicates if the writer supports writing values in segments.
        If true, the write method will be called multiple times until all values have been set
        :return: Partial write support
        """
        return False

    @abstractmethod
    def start(self):
        """
        Starts the writer
        """

    @abstractmethod
    def stop(self):
        """
        Stops the writer
        """

    @abstractmethod
    def write(self, data: List[ValueSet], source_ref: Optional[Source] = None):
        """
        Writes the given data

        :param data: Data which should be exported
        :param source_ref: Reference object which collected the data.
        This is used to detect if a metric has been removed
        """

    def __eq__(self, other):
        if not isinstance(other, Writer):
            return False
        return other.config == self.config

    def __ne__(self, other):
        return not self.__eq__(other)


class DryRunWriter(Writer):
    def __init__(self, name: str):
        super().__init__(None)
        self._name = name

    def supports_partial_write(self) -> bool:
        return True

    def stop(self):
        pass

    def start(self):
        pass

    def write(self, data: List[ValueSet], source_ref: object = None):
        list_items = '\n###\n'.join([str(value_set) for value_set in data])
        self.log.info('[{}] Would write {}'.format(self._name, list_items))


class InMemoryWriter(Writer):
    """
    Appends data to a list
    """

    def __init__(self, config):
        super().__init__(config)
        self.data = []
        self.write_calls = 0

    def start(self):
        pass

    def stop(self):
        pass

    def write(self, data: List[ValueSet], source_ref: object = None):
        self.write_calls += 1
        self.data.append(data)


class ParallelInMemoryWriter(InMemoryWriter):

    def supports_partial_write(self) -> bool:
        return True
