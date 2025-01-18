from unittest import TestCase

from pollect.Requirements import DependencyRequirements
from pollect.core.Factories import SourceFactory, WriterFactory


class TestRequirements(TestCase):

    def test_error_msg(self):
        factory = SourceFactory({})
        # We don't have those dependencies installed in CI/CD
        try:
            factory.create({'type': 'Fritz'})
        except AttributeError as e:
            self.assertIn('fritzconnection', str(e))
            return
        self.fail('No exception raised')

    def test_all_defined(self):
        """
        Makes sure all modules got requirements defined
        """
        requirements = DependencyRequirements()
        factory = SourceFactory({})
        # Check all sources
        for file in factory._object_factory._files:
            if file == 'Source' or file == '__init__':
                continue

            self.assertTrue(file in requirements.deps, file + ' has no dependencies defined')

        factory = WriterFactory()
        # Check all sources
        for file in factory._object_factory._files:
            if file == 'Writer' or file == '__init__':
                continue

            self.assertTrue(file in requirements.deps, file + ' has no dependencies defined')

    def test_no_unused_dependencies(self):
        requirements = DependencyRequirements()
        factory = SourceFactory({})
        # Check all sources
        all_files = []
        all_files.extend(factory._object_factory._files)
        factory = WriterFactory()
        all_files.extend(factory._object_factory._files)

        for name, deps in requirements.deps.items():
            self.assertTrue(name in all_files, name+' dependency defined but not as module found')
            self.assertTrue(len(deps) == 0 or deps[0] != '')

