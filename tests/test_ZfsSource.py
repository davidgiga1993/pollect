import pathlib
from unittest import TestCase
from unittest.mock import patch

from pollect.sources.ZfsSource import ZfsSource


class TestSmartCtl(TestCase):

    def setUp(self) -> None:
        self._own = pathlib.Path(__file__).parent.resolve()

    @patch('pollect.sources.SmartCtlSource.subprocess.check_output')
    def test_parse(self, mock_check_output):
        mock_check_output.return_value = "pool1	5975907581952	24020144013312	85	290	348241	14127899\n" \
            .encode('utf-8')

        data = {'type': '-'}
        source = ZfsSource(data)
        results = source.probe()
        self.assertEqual(2, len(results))
        self.assertEqual(2, len(results[0].values))
        self.assertEqual('capacity', results[0].values[0].name)
        self.assertEqual("pool1", results[0].values[0].label_values[0])
        self.assertEqual("used", results[0].values[0].label_values[1])
        self.assertEqual(5975907581952, results[0].values[0].value)

        self.assertEqual("free", results[0].values[1].label_values[1])
        self.assertEqual(24020144013312, results[0].values[1].value)

        self.assertEqual(4, len(results[1].values))
        self.assertEqual('operations', results[1].values[0].name)
        self.assertEqual(85, results[1].values[0].value)
        self.assertEqual(290, results[1].values[1].value)
        self.assertEqual(348241, results[1].values[2].value)
        self.assertEqual(14127899, results[1].values[3].value)
