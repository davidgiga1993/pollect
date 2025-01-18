import os
from os import listdir
from os.path import isfile
from typing import List

from pollect.Requirements import DependencyRequirements
from pollect.core.Log import Log
from pollect.sources.Source import Source
from pollect.writers.Writer import Writer, DryRunWriter


class ObjectFactory(Log):
    """
    Generic factory for creating objects
    """

    def __init__(self, base_name: str):
        super().__init__()
        self._base_module = base_name
        self._files = self._get_files()
        self._modules = self._get_modules(self._files)

    def create(self, class_name: str, *init_args) -> object:
        """
        Tries to create an instance of the given class name
        :param class_name: Class name
        :param init_args: Constructor arguments
        :return: Object
        """
        class_obj = self._get_class_obj(class_name)
        if class_obj is None:
            # Check if we know the dependencies
            text = DependencyRequirements().get_dependencies_as_text(class_name)
            raise AttributeError(f'Class {class_name} not found in module {self._base_module} - missing dependencies?\n'
                                 f'{text}\n\n'
                                 f'Try running with --debug for more details\n')
        return class_obj(*init_args)

    def _get_files(self) -> List[str]:
        """
        Returns all source files which match the given base name
        :return: List of python files without extension
        """
        base = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', self._base_module))
        file_suffix = '.py'
        files = [f[:-3] for f in listdir(base) if isfile(os.path.join(base, f)) and f.endswith(file_suffix)]
        return files

    def _get_modules(self, files: List[str]) -> List[object]:
        """
        Tries to the given list of files
        """
        modules = []
        for file in files:
            try:
                modules.append(self._import('pollect.' + self._base_module + '.' + file))
            except ImportError as e:
                self.log.debug('Could not import {}: {}'.format(file, str(e)))
                continue
        return modules

    @staticmethod
    def _import(package_name: str):
        return __import__(package_name, fromlist=[package_name])

    def _get_class_obj(self, class_name: str):
        if '.' in class_name:
            # The class specifies an absolute package import
            module_obj = self._import(class_name)
            # The class name must be the same as the file name (aka package)
            class_name = class_name.split('.')[-1]
            try:
                return getattr(module_obj, class_name)
            except AttributeError:
                return None

        # Search for the class in all known modules
        for module_obj in self._modules:
            try:
                return getattr(module_obj, class_name)
            except AttributeError:
                continue
        return None


class SourceFactory:
    def __init__(self, global_conf):
        self.global_conf = global_conf
        self._object_factory = ObjectFactory('sources')

    def create(self, source_data):
        source_type = source_data.get('type')
        class_name = source_type + 'Source'
        source_obj = self._object_factory.create(class_name, source_data)
        if not isinstance(source_obj, Source):
            raise TypeError('Class ' + class_name + ' does not inherit from "Source"')
        source_obj.setup_source(self.global_conf)
        return source_obj


class WriterFactory:
    """
    Factory for creating writer objects
    """

    def __init__(self, dry_run: bool = False):
        self._writer_cache = {}
        """
        Cache for writer singleton objects
        """
        self._object_factory = ObjectFactory('writers')
        self._dry_run = dry_run

    def create(self, writer_config):
        """
        Creates a new writer object from the given writer config.
        If a same writer with the same config does already exist, the same object will be returned

        :param writer_config: Writer configuration dict
        :type writer_config: dict(str, obj)
        :return: Writer object
        :rtype: Writer
        """
        class_name = writer_config.get('type') + 'Writer'
        if self._dry_run:
            return DryRunWriter(class_name)

        writer = self._object_factory.create(class_name, writer_config)
        if not isinstance(writer, Writer):
            raise TypeError('Class ' + class_name + ' does not inherit from "Writer"')
        old_writers = self._writer_cache.get(class_name)
        if old_writers is None:
            # New class type
            writer.start()
            self._writer_cache[class_name] = [writer]
            return writer

        for old_writer in old_writers:
            if old_writer == writer:
                # An old writer object has the same config - reuse it
                return old_writer

        # New writer - add it to the singleton cache
        writer.start()
        self._writer_cache[class_name].append(writer)
