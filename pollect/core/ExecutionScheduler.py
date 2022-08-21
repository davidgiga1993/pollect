import time
from typing import List

import schedule

from pollect.core.Core import Configuration, Executor


class ExecutionScheduler:
    """
    Schedules the executors
    """

    def __init__(self, config: Configuration, executors: List[Executor]):
        self.config = config
        self.executors = executors
        self._active = False

    def create(self):
        """
        Creates the schedulers for the executors
        """
        for executor in self.executors:
            exec_time = executor.tick_time
            if exec_time <= 0:
                # Use global tick time
                schedule.every(self.config.tick_time).seconds.do(executor.execute)
                continue

            # Executor has its own tick time defined
            schedule.every(exec_time).seconds.do(executor.execute)

    def run(self):
        """
        Starts the scheduling
        """
        self._active = True
        # Run them all once at the beginning
        schedule.run_all()
        while self._active:
            schedule.run_pending()
            time.sleep(1)

    def stop(self):
        """
        Stops the scheduling and terminates all probes
        """
        self._active = False
        for executor in self.executors:
            executor.shutdown()
