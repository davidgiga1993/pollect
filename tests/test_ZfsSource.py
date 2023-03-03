import pathlib
from time import sleep
from unittest import TestCase, mock
from unittest.mock import patch

from pollect.sources.ZfsSource import ZfsSource


class TestZfsSource(TestCase):

    def setUp(self) -> None:
        self._own = pathlib.Path(__file__).parent.resolve()

    @patch('pollect.sources.ZfsSource.subprocess.Popen')
    def test_parse(self, mock_subproc_popen):
        process_mock = mock.Mock()
        reads = 0

        def poll():
            nonlocal reads
            if reads == 0:
                reads += 1
                return None
            return 0

        attrs = {"communicate.return_value": ("output", "error"),
                 "poll": poll,
                 "stdout.readline.return_value": "pool1	5975907581952	24020144013312	85	290	348241	14127899\n".encode(
                     'utf-8'),
                 }
        process_mock.configure_mock(**attrs)
        mock_subproc_popen.return_value = process_mock

        data = {'type': '-'}
        source = ZfsSource(data)
        source.setup({})
        sleep(1)
        results = source.probe()
        source.shutdown()
        self.assertEqual(2, len(results))
        self.assertEqual(2, len(results[0].values))
        self.assertEqual('capacity', results[0].values[0].name)
        self.assertEqual("pool1", results[0].values[0].label_values[0])
        self.assertEqual("used", results[0].values[0].label_values[1])
        self.assertEqual(5975907581952, results[0].values[0].value)

        self.assertEqual("free", results[0].values[1].label_values[1])
        self.assertEqual(24020144013312, results[0].values[1].value)

        self.assertEqual(4, len(results[1].values))
        self.assertEqual('operations_per_sec', results[1].values[0].name)
        self.assertEqual(85, results[1].values[0].value)
        self.assertEqual(290, results[1].values[1].value)
        self.assertEqual(348241, results[1].values[2].value)
        self.assertEqual(14127899, results[1].values[3].value)
