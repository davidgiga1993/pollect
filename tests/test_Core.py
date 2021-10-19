import os
from time import sleep
from unittest import TestCase

import schedule

from pollect.core.Core import Configuration
from pollect.core.ExecutionScheduler import ExecutionScheduler
from pollect.core.Factories import SourceFactory, WriterFactory
from pollect.writers.Writer import InMemoryWriter


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
                    ]
                }
            ]
        }
        os.environ['VALUE'] = '10'

        config = Configuration(raw_config)
        executors = config.create_executors()
        scheduler = ExecutionScheduler(config, executors)
        scheduler.create()
        sleep(1)
        schedule.run_pending()

        self.assertIsInstance(config.writer, InMemoryWriter)
        data = config.writer.data
        self.assertGreater(len(data), 0)
        self.assertEqual('10', data[0][0].values[0].value)

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
                            "url": "https://google.com",
                            "timeout": 1
                        },
                    ]
                }
            ]
        }
        config = Configuration(raw_config)
        executors = config.create_executors()
        scheduler = ExecutionScheduler(config, executors)
        scheduler.create()
        sleep(1)
        schedule.run_pending()

        self.assertIsInstance(config.writer, InMemoryWriter)
        data = config.writer.data
        self.assertGreater(len(data), 0)
