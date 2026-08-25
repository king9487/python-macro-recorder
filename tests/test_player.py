import threading
import time
import unittest

from macro_recorder.models import MacroEvent
from macro_recorder.player import MacroPlayer


class FakeKeyboard:
    def __init__(self): self.calls = []
    def press(self, key): self.calls.append(("press", key))
    def release(self, key): self.calls.append(("release", key))


class FakeMouse:
    def __init__(self): self._position = None; self.calls = []
    @property
    def position(self): return self._position
    @position.setter
    def position(self, value): self._position = value; self.calls.append(("position", value))
    def press(self, button): self.calls.append(("press", button))
    def release(self, button): self.calls.append(("release", button))
    def scroll(self, dx, dy): self.calls.append(("scroll", dx, dy))


class PlayerTests(unittest.TestCase):
    def test_repeat_and_dispatch(self):
        keyboard = FakeKeyboard()
        mouse = FakeMouse()
        player = MacroPlayer(keyboard, mouse)
        done = threading.Event()
        player.start([MacroEvent(type="keyboard", action="down", key="a")], 2, 1.0,
                     lambda _cancelled, _error: done.set())
        self.assertTrue(done.wait(1))
        self.assertEqual(len(keyboard.calls), 2)

    def test_long_delay_is_quickly_cancelled(self):
        player = MacroPlayer(FakeKeyboard(), FakeMouse())
        done = threading.Event()
        result = []
        player.start([MacroEvent(type="mouse", action="move", x=1, y=2, delay=5)], 1, 1.0,
                     lambda cancelled, error: (result.append((cancelled, error)), done.set()))
        time.sleep(0.03)
        started = time.monotonic()
        player.stop()
        self.assertTrue(done.wait(0.3))
        self.assertLess(time.monotonic() - started, 0.3)
        self.assertEqual(result, [(True, None)])

    def test_repeat_interval_is_interruptible(self):
        player = MacroPlayer(FakeKeyboard(), FakeMouse())
        done = threading.Event()
        result = []
        player.start([MacroEvent(type="mouse", action="move", x=1, y=2)], 2, 1.0,
                     lambda cancelled, error: (result.append((cancelled, error)), done.set()),
                     repeat_interval=5)
        time.sleep(0.03)
        player.stop()
        self.assertTrue(done.wait(0.3))
        self.assertEqual(result, [(True, None)])


if __name__ == "__main__":
    unittest.main()
