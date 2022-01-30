from typing import List, Optional


class Value:
    """
    Represents a single value
    """

    value: float = 0
    """
    Current value
    """

    name: Optional[str] = None
    """
    Name of this value
    """

    label_values: List[str]
    """
    Values for the labels
    """

    def __init__(self, value: any, label_values: list = None, name: str = None):
        """
        Creates a new value
        :param value: Value (might be bool or float/int)
        :param label_values: The label values
        :param name: Name of this specific value, if None the ValueSet name will be used
        """
        if isinstance(value, bool):
            self.value = 1 if value else 0
        else:
            self.value = value

        self.name = name
        self.label_values = [] if label_values is None else label_values  # type: List[str]

    def get_key(self) -> str:
        """
        Returns the unique key of this value
        :return: Key
        """
        return self.name + ''.join(self.label_values)

    def __repr__(self):
        return str(self.value) + ' (' + str(self.name) + ', ' + str(self.label_values) + ')'


class AvgValue:
    """
    Calculates the average of multiple values
    """
    count: int = 0
    sum: float = 0
    base: Value

    def __init__(self, base: Value):
        self.base = base
        self.add(base)

    def add(self, value: Value):
        self.sum += value.value
        self.count += 1

    def avg(self) -> float:
        return self.sum / self.count


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
