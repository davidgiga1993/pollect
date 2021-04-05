from typing import List, Optional


class Value:
    def __init__(self, value: any, label_values: list = None, name: str = None):
        if isinstance(value, bool):
            self.value = 1 if value else 0
        else:
            self.value = value  # type: float

        self.name = name  # type: Optional[str]
        self.label_values = label_values  # type: Optional[List[str]]

    def __repr__(self):
        return str(self.value) + ' (' + str(self.name) + ', ' + str(self.label_values) + ')'


class ValueSet:
    labels: List[str] = []
    values: List[Value] = []
    time: int = 0
    name: str = ''
    """
    Name of this value set
    """

    def __init__(self, labels: Optional[List[str]] = None):
        self.values = []
        self.labels = []
        if labels is not None:
            self.labels = labels

    def add(self, value: Value):
        self.values.append(value)

    def __repr__(self):
        return self.name + ' ' + str(self.labels) + '\n\t' + '\n\t'.join([str(value) for value in self.values])
