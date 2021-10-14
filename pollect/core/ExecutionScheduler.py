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

        # Run them all once at the beginning
        schedule.run_all()
        while True:
            schedule.run_pending()
            time.sleep(10)
