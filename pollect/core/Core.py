from __future__ import annotations

import time
import traceback
from typing import List, Dict, Optional

from pollect.core.Factories import WriterFactory, SourceFactory
from pollect.core.Log import Log
from pollect.sources.Source import Source
from pollect.sources.helper.ConfigContainer import ConfigContainer
from pollect.writers.Writer import Writer


class Configuration:
    """
    General configuration
    """

    writer: Optional[Writer] = None
    """
    Global data writer which should be used by default
    """

    def __init__(self, config, dry_run: bool = False):
        self.config = ConfigContainer(config)
        self.tick_time = self.config.get('tickTime', 10)
        """
        Time for a single probe tick in seconds
        
        :type tick_time: int
        """

        self.writer_factory = WriterFactory(dry_run)

        writer_config = self.config.get('writer')
        if writer_config is not None:
            self.writer = self.writer_factory.create(writer_config)

    def create_executors(self):
        executors = []
        source_factory = SourceFactory(self)
        for item in self.config.get('executors'):
            executor = Executor(item, self)
            executor.create_writer(self.writer, self.writer_factory)
            executor.initialize_objects(source_factory)
            executors.append(executor)
        return executors


class Executor(Log):
    """
    Executes probes
    """

    config: Dict[str, any]
    writer: Writer
    tick_time: int = 0
    collection_name: str
    global_config: Configuration

    _sources: List[Source] = []
    """
    List of all sources which should be probed
    """

    def __init__(self, exec_config: Dict[str, any], global_config: Configuration):
        super().__init__()
        self.config = exec_config
        self.tick_time = int(self.config.get('tickTime', 0))
        self.collection_name = exec_config.get('collection')
        self.global_config = global_config
        self._sources = []

    def create_writer(self, writer: Optional[Writer], writer_factory: WriterFactory):
        writer_config = self.config.get('writer')
        if writer_config is None and writer is None:
            raise KeyError('No global or local writer configuration not found')
        if writer_config is None:
            # Use default writer
            self.writer = writer
            return

        self.writer = writer_factory.create(writer_config)

    def initialize_objects(self, factory: SourceFactory):
        """
        Initializes all source objects for the execution phase

        :param factory: Factory for creating the source objects
        """
        source_items = self.config.get('sources')
        sources = []
        for item in source_items:
            source = factory.create(item)
            if source is None:
                raise KeyError('Source of type ' + str(item) + ' not found')
            sources.append(source)
        self._sources = sources

    def execute(self):
        """
        Probes all data sources and writes the data using the current writer
        """
        data = []
        # Probe the actual data
        for source in self._sources:
            assert isinstance(source, Source)
            self.log.info(f'Collecting data from {source}')
            now = int(time.time())
            try:
                value_sets = source.probe()
                delta = int(time.time()) - now
                if delta > 10:
                    self.log.warning(f'Probing of {source} took {delta} seconds')

            except Exception as e:
                # Catch all errors that could occur and ignore them
                traceback.print_exc()
                self.log.error(f'Error while probing using source {source}: {e}')
                continue
            if value_sets is None:
                continue

            for value_set in value_sets:
                value_set.time = now
                if len(value_set.name) > 0:
                    value_set.name = self.collection_name + '.' + value_set.name
                else:
                    value_set.name = self.collection_name
                data.append(value_set)

        if len(data) == 0:
            return

        # Write the data
        self.log.info('Writing data...')
        self.writer.write(data)
