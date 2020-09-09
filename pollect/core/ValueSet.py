from typing import List, Optional


class Value:
    def __init__(self, value: float, label_values: list = None, name: str = None):
        self.value = value  # type: float
        self.name = name  # type: Optional[str]
        self.label_values = label_values  # type: Optional[List[str]]

    def __repr__(self):
        return str(self.value) + ' (' + str(self.name) + ', ' + str(self.label_values) + ')'


class ValueSet:
    def __init__(self, labels: list = []):
        self.labels = labels  # type: Optional[List[str]]
        self.values = []  # type: List[Value]
        self.time = 0  # type: int
        self.name = ''  # type: str
        """
        Name of this value set
        """

    def add(self, value: Value):
        self.values.append(value)

    def __repr__(self):
        return self.name + ' ' + str(self.labels) + '\n\t' + '\n\t'.join([str(value) for value in self.values])
