from typing import List, Optional


class Value:
    """
    Represents a single value
    """

    def __init__(self, value: any, label_values: list = None, name: str = None):
        """
        Creates a new value
        :param value: Value (may be bool or float/int)
        :param label_values: The label values
        :param name: Name of this specific value, if None the ValueSet name will be used
        """
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
    """
    Label names
    """

    values: List[Value] = []
    """
    All values in this set
    """

    time: int = 0
    """
    Timestamp when the measurement was made
    """

    name: str = ''
    """
    Name of this value set
    """

    def __init__(self, labels: Optional[List[str]] = None):
        """
        Creates a new value set
        :param labels: Labels of this value set
        """
        self.values = []
        self.labels = []
        if labels is not None:
            self.labels = labels

    def add(self, value: Value):
        """
        Adds a new value to this set
        :param value: Value
        """
        self.values.append(value)

    def __repr__(self):
        return self.name + ' ' + str(self.labels) + '\n\t' + '\n\t'.join([str(value) for value in self.values])
