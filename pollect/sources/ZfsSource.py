import subprocess
from typing import List, Dict

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class ZpoolIostat:
    @staticmethod
    def get_stats(pool: str = None) -> Dict[str, Dict[str, Dict[str, int]]]:
        args = ['zpool', 'iostat', '-Hp']
        if pool is not None:
            args.append(pool)
        output = subprocess.check_output(args).decode('utf-8')
        lines = output.split('\n')

        data: Dict[str, Dict[str, Dict[str, int]]] = {}
        for line in lines:
            segments = line.split('\t')
            if len(segments) < 7:
                continue
            pool = segments[0]
            data[pool] = {
                'capacity': {
                    'used': int(segments[1]),
                    'free': int(segments[2]),
                },
                'operations': {
                    'read': int(segments[3]),
                    'write': int(segments[4]),
                },
                'bandwidth': {
                    'read': int(segments[5]),
                    'write': int(segments[6]),
                }
            }
        return data


class ZfsSource(Source):
    def __init__(self, config):
        super().__init__(config)

    def _probe(self) -> List[ValueSet]:
        capacity_set = ValueSet(labels=['pool', 'capacity'])
        io_set = ValueSet(labels=['pool', 'io'])
        stats = ZpoolIostat.get_stats()
        for pool, data in stats.items():
            capacity = data['capacity']
            for key, value in capacity.items():
                capacity_set.add(Value(value, [pool, key], 'capacity'))

            operations = data['operations']
            for key, value in operations.items():
                io_set.add(Value(value, [pool, key], 'operations'))

            operations = data['bandwidth']
            for key, value in operations.items():
                io_set.add(Value(value, [pool, key], 'bandwidth'))

        return [capacity_set, io_set]
