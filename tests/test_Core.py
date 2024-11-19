import datetime
import os
import threading
from time import sleep
from typing import Dict, Callable
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

    def test_exec(self):
        test = IntegrationTest()
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
                        {
                            "type": "Dummy",
                            "callback": test.stop_callback,
                        },
                    ]
                }
            ]
        }

        def run(config: Configuration):
            writer = config.writers[0]
            self.assertIsInstance(writer, InMemoryWriter)
            data = writer.data
            self.assertGreater(len(data), 0)

        test.run(raw_config, run)

    def test_resolve(self):
        test = IntegrationTest()
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
                        {
                            "type": "Dummy",
                            "callback": test.stop_callback,
                        },
                    ]
                }
            ]
        }
        os.environ['VALUE'] = '10'

        def run(config: Configuration):
            writer = config.writers[0]
            self.assertIsInstance(writer, InMemoryWriter)
            data = writer.data
            self.assertEqual(writer.write_calls, 1)
            self.assertGreater(len(data), 0)
            self.assertEqual('10', data[0][0].values[0].value)
            self.assertEqual('1', data[0][1].values[0].value)

        test.run(raw_config, run)

    def test_exec_partial_prometheus(self):
        test = IntegrationTest()

        def verify():
            sleep(4)
            try:
                reply = requests.get('http://localhost:9123')
                self.assertIn('github', reply.text)
                self.assertIn('google', reply.text)
                test.stop_pollect()
            except Exception as e:
                self.fail(e)

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
                        {
                            "type": "Dummy",
                            "callback": verify,
                        },
                    ]
                }
            ]
        }

        test.run(raw_config, None)

    def test_exec_parallel(self):
        self.first_ts = None
        self.second_ts = None
        test = IntegrationTest()

        def first_callback():
            self.first_ts = datetime.datetime.now()
            if self.second_ts is not None:
                test.stop_callback()

        def second_callback():
            self.second_ts = datetime.datetime.now()
            if self.first_ts is not None:
                test.stop_callback()

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
                            "callback": first_callback,
                        },
                        {
                            "type": "Dummy",
                            "value": 2,
                            "sleep": 2,
                            "callback": second_callback,
                        }
                    ]
                }
            ]
        }

        def verify(config: Configuration):
            writer = config.writers[0]
            self.assertIsInstance(writer, ParallelInMemoryWriter)
            data = writer.data
            self.assertEqual(writer.write_calls, 2)
            self.assertEqual(len(data), 2)

        test.run(raw_config, verify)
        self.assertTrue((self.first_ts - self.second_ts).total_seconds() < 1)

    def test_parallel_executor(self):
        test = IntegrationTest()
        self.b = None
        self.a1 = None
        self.a2 = None

        def verify_complete():
            if self.a1 is not None and self.a2 is not None and self.b is not None:
                test.stop_callback()

        def callback_b():
            if self.b is None:
                self.b = datetime.datetime.now()
            verify_complete()

        def callback_a1():
            if self.a1 is None:
                self.a1 = datetime.datetime.now()
            verify_complete()

        def callback_a2():
            if self.a2 is None:
                self.a2 = datetime.datetime.now()
            verify_complete()

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
                            "sleep": 1,
                            "callback": callback_a1
                        },
                        {
                            "type": "Dummy",
                            "value": 2,
                            "sleep": 1,
                            "callback": callback_a2
                        }
                    ]
                },
                {
                    "collection": "b",
                    "sources": [
                        {
                            "type": "Dummy",
                            "value": 4,
                            "callback": callback_b
                        },
                    ]
                }
            ]
        }

        def verify(config: Configuration):
            collection_delta = (self.a1 - self.b).total_seconds()
            self.assertTrue(collection_delta < 2)
            self.assertTrue((self.a2 - self.a1).total_seconds() < 2)
            self.assertTrue((self.a2 - self.b).total_seconds() > 2)

        test.run(raw_config, verify)

    @staticmethod
    def _run_and_stop_old(executor: ExecutionScheduler, wait_time: int, call):
        executor.create()
        threading.Thread(target=executor.run).start()
        sleep(wait_time)
        try:
            call()
        finally:
            executor.stop()


class IntegrationTest:
    scheduler: ExecutionScheduler
    config: Configuration

    def stop_callback(self):
        self.stop_pollect()

    def stop_pollect(self):
        self.scheduler.stop()

    def run(self, raw_config: Dict[str, any], post_callback: Callable):
        self.config = Configuration(raw_config)
        executors = self.config.create_executors()
        self.scheduler = ExecutionScheduler(self.config, executors)
        self.scheduler.create()
        thread = threading.Thread(target=self.scheduler.run, name='pollect-root°')
        thread.start()
        thread.join(15)
        if thread.is_alive():
            raise Exception('pollect did not terminate')

        if post_callback is not None:
            post_callback(self.config)
