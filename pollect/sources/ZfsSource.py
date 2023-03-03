import subprocess
import threading
from typing import List

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class ZpoolIostat:
    def __init__(self):
        self._ticks = 0
        self._active = False
        self._sets: List[ValueSet] = [ValueSet(labels=['pool', 'capacity']), ValueSet(labels=['pool', 'io'])]

    def start(self, pool: str = None):
        self._active = True
        args = ['zpool', 'iostat', '-Hp', '10']  # 10 second interval
        if pool is not None:
            args.append(pool)

        threading.Thread(target=self._run_process, args=[args]).start()

    def _run_process(self, args):
        process = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        while process.poll() is None and self._active:
            capacity_set = ValueSet()
            io_set = ValueSet()
            line = process.stdout.readline().decode('utf-8')
            segments = line.split('\t')
            if len(segments) < 7:
                continue

            pool = segments[0]
            capacity_set.add(Value(int(segments[1]), [pool, 'used'], 'capacity'))
            capacity_set.add(Value(int(segments[2]), [pool, 'free'], 'capacity'))

            io_set.add(Value(int(segments[3]), [pool, 'read'], 'operations_per_sec'))
            io_set.add(Value(int(segments[4]), [pool, 'write'], 'operations_per_sec'))

            io_set.add(Value(int(segments[5]), [pool, 'read'], 'bandwidth_per_sec'))
            io_set.add(Value(int(segments[6]), [pool, 'write'], 'bandwidth_per_sec'))
            self._add_data([capacity_set, io_set])

    def stop(self):
        self._active = False

    def get_data(self) -> List[ValueSet]:
        """
        Returns the data as units/second
        :return: Data
        """
        output: List[ValueSet] = []
        for value_set in self._sets:
            new_set = ValueSet(labels=value_set.labels)
            output.append(new_set)
            for value in value_set.values:
                new_set.values.append(Value(value.value / self._ticks, value.label_values, value.name))

        self._ticks = 0
        return output

    def _add_data(self, sets: List[ValueSet]):
        """
        Adds the given value sets to the instance values sets.
        This assumes that the order of the value sets and their values never changes.

        :param sets: Sets which values should be added
        """
        self._ticks += 1
        if self._ticks == 1:
            # First value - just copy the values
            for s in range(len(self._sets)):
                self._sets[s].values = sets[s].values
            return

        for s in range(len(self._sets)):
            source_values: List[Value] = sets[s].values
            dest_values: List[Value] = self._sets[s].values
            for v in range(len(source_values)):
                dest_values[v].value += source_values[v].value


class ZfsSource(Source):
    def __init__(self, config):
        super().__init__(config)
        self._iostats = ZpoolIostat()

    def setup(self, global_conf):
        self._iostats.start()

    def shutdown(self):
        self._iostats.stop()

    def _probe(self) -> List[ValueSet]:
        self.log.info('Probing...')
        return self._iostats.get_data()
