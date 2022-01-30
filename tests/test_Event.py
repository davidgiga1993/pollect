from unittest import TestCase

from pollect.core.events.Event import Event


class TestEvent(TestCase):
    def test_fire(self):
        calls = 0

        def callback():
            nonlocal calls
            calls += 1

        event = Event()
        event += callback
        event.fire()
        self.assertEqual(1, calls)

    def test_add_remove(self):
        calls = 0

        def callback():
            nonlocal calls
            calls += 1

        event = Event()
        event += callback
        event -= callback
        event.fire()
        self.assertEqual(0, calls)

    def test_args(self):
        calls = 0

        def callback(arg1, arg2):
            nonlocal calls
            calls += arg1 + arg2

        event = Event()
        event += callback
        event.fire(1, 2)
        self.assertEqual(3, calls)

    def test_kwargs(self):
        calls = 0

        def callback(arg1, arg2, other=0, named=0):
            nonlocal calls
            calls += arg1 + arg2 + named

        event = Event()
        event += callback
        event.fire(1, 2, named=2)
        self.assertEqual(5, calls)
