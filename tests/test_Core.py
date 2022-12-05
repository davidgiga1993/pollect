import os
import threading
from time import sleep
from unittest import TestCase

import requests

from pollect.core.Core import Configuration
from pollect.core.ExecutionScheduler import ExecutionScheduler
from pollect.core.Factories import SourceFactory, WriterFactory
from pollect.writers.Writer import InMemoryWriter, ParallelInMemoryWriter


class TestCore(TestCase):
    def setUp(self):
        if 'Pollect' not in os.getcwd():
            os.chdir(os.path.abspath(os.path.join(os.getcwd(), '..')))

    def test_source_factory(self):
        factory = SourceFactory(None)
        self.assertIsNotNone(factory.create({'type': 'Bind'}))

    def test_writers_factory(self):
        factory = WriterFactory(False)
        self.assertIsNotNone(factory.create({'type': 'DryRun'}))

    def test_resolve(self):
        raw_config = {
            "tickTime": 1,
            "writer": {
                "type": "InMemory"
            },
            "executors": [
                {
                    "collection": "pollect",
                    "sources": [
                        {
                            "type": "Dummy",
                            "value": "${VALUE}",
                        },
                        {
                            "type": "Dummy",
                            "value": "1",
                        },
                    ]
                }
            ]
        }
        os.environ['VALUE'] = '10'

        config = Configuration(raw_config)
        executors = config.create_executors()
        scheduler = ExecutionScheduler(config, executors)

        def run():
            self.assertIsInstance(config.writer, InMemoryWriter)
            data = config.writer.data
            self.assertEqual(config.writer.write_calls, 1)
            self.assertGreater(len(data), 0)
            self.assertEqual('10', data[0][0].values[0].value)
            self.assertEqual('1', data[0][1].values[0].value)

        self._run_and_stop(scheduler, 1, run)

    def test_exec(self):
        raw_config = {
            "tickTime": 1,
            "writer": {
                "type": "InMemory"
            },
            "executors": [
                {
                    "collection": "pollect",
                    "sources": [
                        {
                            "type": "Http",
                            "name": "dev_core",
                            "url": ["https://google.com"],
                            "timeout": 1
                        },
                    ]
                }
            ]
        }
        config = Configuration(raw_config)
        executors = config.create_executors()
        scheduler = ExecutionScheduler(config, executors)

        def run():
            self.assertIsInstance(config.writer, InMemoryWriter)
            data = config.writer.data
            self.assertGreater(len(data), 0)

        self._run_and_stop(scheduler, 1, run)

    def test_exec_partial_prometheus(self):
        raw_config = {
            "tickTime": 1,
            "threads": 2,
            "writer": {
                "type": "Prometheus",
                "port": 9123,
            },
            "executors": [
                {
                    "collection": "pollect",
                    "sources": [
                        {
                            "type": "Http",
                            "name": "dev_core",
                            "url": ["https://google.com", "https://github.com"],
                            "timeout": 1
                        },
                    ]
                }
            ]
        }
        config = Configuration(raw_config)
        executors = config.create_executors()
        scheduler = ExecutionScheduler(config, executors)

        def run():
            sleep(4)
            reply = requests.get('http://localhost:9123')
            self.assertIn('github', reply.text)
            self.assertIn('google', reply.text)

        self._run_and_stop(scheduler, 1, run)

    def test_exec_parallel(self):
        raw_config = {
            "tickTime": 30,
            "threads": 2,
            "writer": {
                "type": "ParallelInMemory"
            },
            "executors": [
                {
                    "collection": "pollect",
                    "sources": [
                        {
                            "type": "Dummy",
                            "value": 1,
                            "sleep": 2,
                        },
                        {
                            "type": "Dummy",
                            "value": 2,
                            "sleep": 2,
                        }
                    ]
                }
            ]
        }
        config = Configuration(raw_config)
        executors = config.create_executors()
        scheduler = ExecutionScheduler(config, executors)

        def run():
            self.assertIsInstance(config.writer, ParallelInMemoryWriter)
            # Wait for the jobs to complete
            sleep(2.5)
            data = config.writer.data
            self.assertEqual(config.writer.write_calls, 2)
            self.assertEqual(len(data), 2)

        self._run_and_stop(scheduler, 1, run)

    def test_parallel_executor(self):
        raw_config = {
            "tickTime": 1,
            "threads": 1,
            "writer": {
                "type": "ParallelInMemory"
            },
            "executors": [
                {
                    "collection": "a",
                    "sources": [
                        {
                            "type": "Dummy",
                            "value": 1,
                            "sleep": 4,
                        },
                        {
                            "type": "Dummy",
                            "value": 2,
                            "sleep": 4,
                        }
                    ]
                },
                {
                    "collection": "b",
                    "sources": [
                        {
                            "type": "Dummy",
                            "value": 4,
                        },
                    ]
                }
            ]
        }
        config = Configuration(raw_config)
        executors = config.create_executors()
        scheduler = ExecutionScheduler(config, executors)

        def run():
            self.assertIsInstance(config.writer, ParallelInMemoryWriter)
            # Wait for the collection b to complete a couple of times
            sleep(2)
            data = config.writer.data
            print(f'Write calls: {config.writer.write_calls}')
            self.assertTrue(config.writer.write_calls >= 2)
            for entry in data:
                for value in entry:
                    self.assertEqual(4, value.values[0].value)
                    pass

        self._run_and_stop(scheduler, 1, run)

    @staticmethod
    def _run_and_stop(executor: ExecutionScheduler, wait_time: int, call):
        executor.create()
        threading.Thread(target=executor.run).start()
        sleep(wait_time)
        try:
            call()
        finally:
            executor.stop()
