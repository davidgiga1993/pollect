class Unit:
    """
    Units
    """

    _prefix: str
    _base: str

    _factor: float

    @staticmethod
    def base(unit: str):
        return Unit('', unit, 1)

    @staticmethod
    def milli(unit: str):
        return Unit('m', unit, 0.001)

    @staticmethod
    def hundredth(unit: str):
        return Unit('t', unit, 0.01)

    @staticmethod
    def tenth(unit: str):
        return Unit('t', unit, 0.1)

    def __init__(self, prefix: str, unit: str, factor: float):
        self._prefix = prefix
        self._base = unit
        self._factor = factor

    def get_unit(self) -> str:
        return self._prefix + self._base

    def get_base(self) -> str:
        return self._base

    def to_base(self, value: float) -> float:
        return value * self._factor


class Ws(Unit):
    """
    Watt/second
    """

    def __init__(self):
        super().__init__('', 'Ws', 1)

    def get_base(self):
        return 'kWh'

    def to_base(self, value: float) -> float:
        # To kWh
        return value / 3600000


class ValueWithUnit:
    value: float
    unit: Unit

    def __init__(self, value: float, unit: Unit):
        self.value = value
        self.unit = unit

    def get_as_base_unit(self) -> float:
        """
        Returns the value in its base unit (for example A instead of mA)
        :return: Value
        """
        if self.unit is None:
            return self.value
        return self.unit.to_base(self.value)

    def __str__(self):
        unit = self.unit.get_base()
        value = self.unit.to_base(self.value)
        return f'{value} {unit}'
