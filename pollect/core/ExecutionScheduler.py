import queue
import threading
import time
from typing import List, Dict

import schedule
from pollect.core.Log import Log

from pollect.core.Core import Configuration, Executor


class ExecutionScheduler(Log):
    """
    Schedules the executors.
    Each executor has its own thread and worker queue
    so different executors can't block each-other during execution
    """
    _queues: Dict[Executor, queue.Queue]

    def __init__(self, config: Configuration, executors: List[Executor]):
        super().__init__()
        self.config = config
        self.executors = executors
        self._active = False
        self._queues = {}
        for executor in executors:
            self._queues[executor] = queue.Queue(2)

    def create(self):
        """
        Creates the schedulers for the executors
        """
        for executor in self.executors:
            exec_time = executor.tick_time
            if exec_time <= 0:
                # Use global tick time
                schedule.every(self.config.tick_time).seconds.do(self._schedule_execution, executor)
                continue

            # Executor has its own tick time defined
            schedule.every(exec_time).seconds.do(self._schedule_execution, executor)

    def run(self):
        """
        Starts the scheduling
        """
        self._active = True
        for executor, exec_queue in self._queues.items():
            worker_thread = threading.Thread(target=self._work_on_queue, args=[executor])
            worker_thread.start()

        # Run them all once at the beginning
        schedule.run_all()
        while self._active:
            schedule.run_pending()
            time.sleep(1)
        self.log.debug('Stopped scheduler execution')

    def _schedule_execution(self, executor: Executor):
        """
        Queues a new executor for execution
        :param executor: Executor to be queued
        """
        exec_queue = self._queues[executor]
        if exec_queue.qsize() >= 1:
            # The queue is already nearly full, don't add anything
            return

        self.log.debug(f'Scheduling execution of {executor.collection_name}')
        exec_queue.put(executor.execute)

    def _work_on_queue(self, executor: Executor):
        """
        Works on the executor queue
        """
        exec_queue = self._queues[executor]
        while self._active:
            job_func = exec_queue.get()
            if job_func is None:
                continue
            job_func()
            exec_queue.task_done()
        self.log.info(f'Stopped working on queue for executor {executor.collection_name}')

    def stop(self):
        """
        Stops the scheduling and terminates all probes
        """
        self._active = False
        for exec_queue in self._queues.values():
            exec_queue.put(None)
        for executor in self.executors:
            executor.shutdown()
