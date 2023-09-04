import json
import pathlib
from unittest import TestCase
from unittest.mock import Mock

from pollect.core.ValueSet import ValueSet
from pollect.sources.EvccSource import EvccSource


class TestEvccSource(TestCase):

    def setUp(self) -> None:
        self._own = pathlib.Path(__file__).parent.resolve()

    def test_parsing(self):
        with open(f'{self._own}/data/evcc.json') as f:
            data = json.load(f)

        source = EvccSource({'host': 'test', 'type': ''})
        source._get_data = Mock()
        source._get_data.return_value = data
        sources = source.probe()

        self.assertEqual(2, len(sources))
        self.assertValue('vehicleSoc', 50, sources[0])
        self.assertValue('targetSoc', 80, sources[0])
        self.assertValue('chargePower', 2373, sources[0])
        self.assertValue('vehiclePresent', 1, sources[0])
        self.assertValue('sessionPricePerKWh',  0.1079, sources[0])
        self.assertValue('phasesActive',  1, sources[0])
        self.assertEqual('Garage', sources[0].values[0].label_values[0])

    def assertValue(self, name: str, value: any, source: ValueSet):
        for val in source.values:
            if val.name == name:
                self.assertEqual(value, val.value, name)
                return
        self.fail(f'Value not found {name}')