import time
import traceback

from pollect.core.Factories import WriterFactory, SourceFactory
from pollect.sources import Log
from pollect.sources.Source import Source


class Configuration:
    """
    General configuration
    """

    def __init__(self, config, dry_run: bool = False):
        self.config = config
        self.tick_time = self.config.get('tickTime', 10)
        """
        Time for a single probe tick in seconds
        
        :type tick_time: int
        """

        self.writer_factory = WriterFactory(dry_run)
        self.writer = None
        """
        Global data writer which should be used by default
        
        :type writer: Writer
        """
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


class Executor:
    def __init__(self, exec_config, global_config: Configuration):
        self.config = exec_config
        self.tick_time = int(self.config.get('tickTime', 0))
        self.collection_name = exec_config.get('collection')
        self.global_config = global_config
        self.writer = None
        """
        Data writer which should be used for this executor
        
        :type writer: Writer
        """

        self._sources = []
        """
        List of all sources which should be probed
        
        :type sources: List[Source]
        """

    def create_writer(self, writer, writer_factory):
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
            Log.info('Collecting data from ' + str(source))
            now = int(time.time())
            try:
                value_sets = source.probe()
                delta = int(time.time()) - now
                if delta > 10:
                    Log.warning('Probing of ' + str(source) + ' took ' + str(delta) + ' seconds')

            except Exception as e:
                # Catch all errors that could occur and ignore them
                traceback.print_exc()
                Log.error('Error while probing using source ' + str(source) + ': ' + str(e))
                continue
            if value_sets is None:
                continue

            for value_set in value_sets:
                value_set.time = now
                value_set.name = self.collection_name + '.' + value_set.name
                data.append(value_set)

        if len(data) == 0:
            return

        # Write the data
        Log.info('Writing data...')
        self.writer.write(data)
