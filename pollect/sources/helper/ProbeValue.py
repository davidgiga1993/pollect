class ProbeValue:
    __slots__ = ['time', 'data']

    def __init__(self, timestamp: float, data: any):
        self.time = timestamp
        self.data = data
