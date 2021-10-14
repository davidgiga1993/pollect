import pickle
import socket
import struct
from abc import abstractmethod
from typing import List

from pollect.core.Log import Log
from pollect.core.ValueSet import ValueSet


class Writer(Log):
    """
    General writer
    """

    def __init__(self, config):
        super().__init__()
        self.config = config

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
    def write(self, data: List[ValueSet]):
        """
        Writes the given data

        :param data: Data which should be exported
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

    def stop(self):
        pass

    def start(self):
        pass

    def write(self, data: List[ValueSet]):
        list_items = '\n###\n'.join([str(value_set) for value_set in data])
        self.log.info('[{}] Would write {}'.format(self._name, list_items))


class GraphiteWriter(Writer):
    """
    Graphite pickle TCP writer
    """

    def __init__(self, config):
        super().__init__(config)
        self.host = config.get('host')
        self.port = config.get('picklePort')
        self.socket = None
        self._retry = 0

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.host, self.port))
        except ConnectionRefusedError as e:
            self.log.error('Could not connect to graphite pickle port')
            raise e

    def stop(self):
        if self.socket is not None:
            self.socket.close()

    def write(self, data):
        payload = pickle.dumps(data, protocol=2)
        header = struct.pack("!L", len(payload))
        message = header + payload
        try:
            self.socket.sendall(message)
        except BrokenPipeError as e:
            self.log.error('Tcp pipe broken - reconnecting')
            if self._retry == 5:
                self.log.error('Could not send data after 5 retries - terminating now')
                raise e

            self._retry += 1
            self.start()
            self.write(data)
            self._retry = 0


class InMemoryWriter(Writer):
    """
    Appends data to a list
    """

    def __init__(self, config):
        super().__init__(config)
        self.data = []

    def start(self):
        pass

    def stop(self):
        pass

    def write(self, data):
        self.data.append(data)
