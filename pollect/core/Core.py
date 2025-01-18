from __future__ import annotations

import time
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from typing import List, Dict, Optional

from pollect.core.Factories import WriterFactory, SourceFactory
from pollect.core.Log import Log
from pollect.core.ValueSet import ValueSet
from pollect.core.config.ConfigContainer import ConfigContainer
from pollect.sources.Source import Source
from pollect.writers.Writer import Writer


class Configuration:
    """
    General configuration
    """
    WRITERS = 'writers'
    WRITER = 'writer'
    SOURCES = 'sources'

    writers: List[Writer] = None
    """
    Global data writers which should be used by default
    """

    tick_time: int
    """
    Time for a single probe tick in seconds       
    """

    def __init__(self, config, dry_run: bool = False):
        self.writers = []
        self.config = ConfigContainer(config)
        self.tick_time = self.config.get('tickTime', 10)
        self.thread_count = self.config.get('threads', 5)

        self.writer_factory = WriterFactory(dry_run)

        writer_configs = self.config.get(self.WRITERS, [])
        writer_config = self.config.get(self.WRITER)
        if writer_config is not None:
            writer_configs.append(writer_config)

        for config in writer_configs:
            self.writers.append(self.writer_factory.create(config))

    def create_executors(self) -> List[Executor]:
        executors = []
        source_factory = SourceFactory(self)
        for item in self.config.get('executors'):
            thread_pool = ThreadPoolExecutor(max_workers=self.thread_count)
            executor = Executor(thread_pool, item, self)
            executor.create_writers(self.writers, self.writer_factory)
            executor.initialize_objects(source_factory)
            executors.append(executor)
        return executors

    def get_all_sources(self) -> List[Dict[str, ConfigContainer]]:
        """
        Returns a list of all defined sources in all executors
        """
        sources = []
        for item in self.config.get('executors'):
            sources.extend(item.get(self.SOURCES, []))
        return sources

    def get_all_writers(self) -> List[Dict[str, ConfigContainer]]:
        """
        Returns a list of all defined writers in all executors
        """
        writers = []
        writers.extend(self.config.get(self.WRITERS, []))
        writers.append(self.config.get(self.WRITER))
        for item in self.config.get('executors'):
            writers.append(item.get(self.WRITER))
        return [w for w in writers if w is not None]


class Executor(Log):
    """
    Executes a collection of probes.
    """

    config: Dict[str, any]
    writers: List[Writer]
    tick_time: int = 0
    collection_name: str
    global_config: Configuration

    _sources: List[Source] = []
    """
    List of all sources which should be probed
    """

    thread_pool: ThreadPoolExecutor
    """
    Thread pool for probing
    """

    def __init__(self, thread_pool: ThreadPoolExecutor, exec_config: Dict[str, any], global_config: Configuration):
        super().__init__()
        self.thread_pool = thread_pool
        self.config = exec_config
        self.tick_time = int(self.config.get('tickTime', 0))
        self.collection_name = exec_config.get('collection')
        self.global_config = global_config
        self._sources = []
        self.writers = []

    def create_writers(self, writers: List[Writer], writer_factory: WriterFactory):
        writer_config = self.config.get(Configuration.WRITER)
        if writer_config is None and len(writers) == 0:
            raise KeyError('No global or local writer configuration not found')
        if writer_config is None:
            # Use default writer
            self.writers.extend(writers)
        else:
            self.writers.append(writer_factory.create(writer_config))

        partial_write = self.writers[0].supports_partial_write()
        if len(self.writers) > 1:
            for writer in self.writers[1:]:
                if partial_write != writer.supports_partial_write():
                    raise ValueError('Multiple writers must all have the same "partial_write" feature support')

    def initialize_objects(self, factory: SourceFactory):
        """
        Initializes all source objects for the execution phase

        :param factory: Factory for creating the source objects
        """
        source_items = self.config.get(Configuration.SOURCES)
        sources = []
        for item in source_items:
            source = factory.create(item)
            if source is None:
                raise KeyError('Source of type ' + str(item) + ' not found')
            sources.append(source)
        self._sources = sources

    def shutdown(self):
        """
        Terminates all sources and writers
        """
        self.log.info(f'Shutting down {self.collection_name}')
        self.thread_pool.shutdown()
        for source in self._sources:
            source.shutdown()
        for writer in self.writers:
            writer.stop()

    def execute(self):
        """
        Probes all data sources and writes the data using the current writer
        """
        self.log.debug(f'Executing {self.collection_name}')
        partial_write = self.writers[0].supports_partial_write()
        futures = []

        for source in self._sources:
            assert isinstance(source, Source)
            future = self.thread_pool.submit(self._probe_and_write if partial_write else self._probe, source)
            futures.append(future)

        if partial_write:
            # Data has already been written to the exporter
            return

        # Wait and merge the results
        data = []
        for future in futures:
            # noinspection PyTypeChecker
            self._merge(future.result(), data)
        self._write(data, None, False)

    def _probe_and_write(self, source: Source):
        """
        Probes a single source and writes the data to the writer
        :param source: Source
        """
        value_sets = self._probe(source)
        data = []
        self._merge(value_sets, data)
        self._write(data, source, True)

    def _probe(self, source: Source) -> List[ValueSet]:
        """
        Probes a single source
        :param source: Source
        :return: The probe result data
        """

        log_tag = f'{self.collection_name}/{source}'
        self.log.info(f'Collecting data from {log_tag}')
        now = int(time.time())
        try:
            value_sets = source.probe()
            delta = int(time.time()) - now
            if delta > 10:
                self.log.warning(f'Probing of {log_tag} took {delta} seconds')
            return value_sets
        except Exception as e:
            # Catch all errors that could occur and ignore them
            traceback.print_exc()
            self.log.error(f'Error while probing using source {log_tag}: {e}')
        return []

    def _merge(self, value_sets: List[ValueSet], results: List[ValueSet]):
        """
        Merges the given value sets
        :param value_sets: Value sets which should be merged
        :param results: Result list
        """
        now = int(time.time())
        for value_set in value_sets:
            value_set.time = now
            if len(value_set.name) > 0:
                value_set.name = self.collection_name + '.' + value_set.name
            else:
                value_set.name = self.collection_name
            results.append(value_set)

    def _write(self, value_sets: List[ValueSet], source_ref: Optional[Source], partial_writers_filter: bool):
        """
        Writes the given value sets using the current exporter
        :param value_sets: Value sets
        :param source_ref: Reference object which collected the data.
        :param partial_writers_filter: True to only write the partial writers, False to write the full writer
        This is used to detect if a metric has been removed
        """
        if len(value_sets) == 0:
            return

        # Write the data
        self.log.debug(f'Writing data for {self.collection_name}')
        for writer in self.writers:
            if partial_writers_filter != writer.supports_partial_write():
                continue
            try:
                writer.write(value_sets, source_ref)
            except Exception as e:
                self.log.error(f'Could not write data: {e}, source: {source_ref}')
