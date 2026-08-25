import threading
import time
import unittest

from macro_recorder.models import MacroEvent
from macro_recorder.player import MacroPlayer


class FakeKeyboard:
    def __init__(self): self.calls = []; self.pressed = threading.Event()
    def press(self, key): self.calls.append(("press", key)); self.pressed.set()
    def release(self, key): self.calls.append(("release", key))


class FakeMouse:
    def __init__(self): self._position = None; self.calls = []; self.pressed = threading.Event()
    @property
    def position(self): return self._position
    @position.setter
    def position(self, value): self._position = value; self.calls.append(("position", value))
    def press(self, button): self.calls.append(("press", button)); self.pressed.set()
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
        self.assertEqual(sum(call[0] == "press" for call in keyboard.calls), 2)
        self.assertEqual(sum(call[0] == "release" for call in keyboard.calls), 1)

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

    def test_keyboard_key_is_released_when_cancelled(self):
        keyboard = FakeKeyboard()
        player = MacroPlayer(keyboard, FakeMouse())
        done = threading.Event()
        events = [
            MacroEvent(type="keyboard", action="down", key="w"),
            MacroEvent(type="keyboard", action="up", key="w", delay=5),
        ]
        player.start(events, 1, 1.0, lambda _cancelled, _error: done.set())
        self.assertTrue(keyboard.pressed.wait(0.3))
        player.stop()
        self.assertTrue(done.wait(0.3))
        self.assertEqual([call[0] for call in keyboard.calls], ["press", "release"])

    def test_mouse_button_is_released_when_cancelled(self):
        mouse = FakeMouse()
        player = MacroPlayer(FakeKeyboard(), mouse)
        done = threading.Event()
        events = [
            MacroEvent(type="mouse", action="down", button="left", x=10, y=20),
            MacroEvent(type="mouse", action="up", button="left", x=10, y=20, delay=5),
        ]
        player.start(events, 1, 1.0, lambda _cancelled, _error: done.set())
        self.assertTrue(mouse.pressed.wait(0.3))
        player.stop()
        self.assertTrue(done.wait(0.3))
        button_calls = [call[0] for call in mouse.calls if call[0] in {"press", "release"}]
        self.assertEqual(button_calls, ["press", "release"])

    def test_normal_playback_leaves_no_tracked_inputs(self):
        keyboard = FakeKeyboard()
        mouse = FakeMouse()
        player = MacroPlayer(keyboard, mouse)
        done = threading.Event()
        events = [
            MacroEvent(type="keyboard", action="down", key="a"),
            MacroEvent(type="keyboard", action="up", key="a"),
            MacroEvent(type="mouse", action="down", button="right", x=1, y=2),
            MacroEvent(type="mouse", action="up", button="right", x=1, y=2),
        ]
        player.start(events, 1, 1.0, lambda _cancelled, _error: done.set())
        self.assertTrue(done.wait(1))
        self.assertFalse(player._pressed_keys)
        self.assertFalse(player._pressed_buttons)

    def test_exception_during_playback_releases_held_input(self):
        class FailingMouse(FakeMouse):
            @FakeMouse.position.setter
            def position(self, value):
                raise RuntimeError("dispatch failed")

        keyboard = FakeKeyboard()
        player = MacroPlayer(keyboard, FailingMouse())
        done = threading.Event()
        result = []
        events = [
            MacroEvent(type="keyboard", action="down", key="a"),
            MacroEvent(type="mouse", action="move", x=1, y=2),
        ]
        player.start(events, 1, 1.0,
                     lambda cancelled, error: (result.append((cancelled, error)), done.set()))
        self.assertTrue(done.wait(1))
        self.assertEqual([call[0] for call in keyboard.calls], ["press", "release"])
        self.assertEqual(result, [(False, "dispatch failed")])

    def test_cleanup_is_idempotent(self):
        keyboard = FakeKeyboard()
        mouse = FakeMouse()
        player = MacroPlayer(keyboard, mouse)
        player._dispatch(MacroEvent(type="keyboard", action="down", key="a"))
        player._dispatch(MacroEvent(type="mouse", action="down", button="left", x=1, y=2))
        self.assertEqual(player.release_all_inputs(), [])
        self.assertEqual(player.release_all_inputs(), [])
        self.assertEqual(sum(call[0] == "release" for call in keyboard.calls), 1)
        self.assertEqual(sum(call[0] == "release" for call in mouse.calls), 1)

    def test_countdown_completes_before_playback(self):
        keyboard = FakeKeyboard()
        player = MacroPlayer(keyboard, FakeMouse())
        done = threading.Event()
        countdown = []
        player.start([MacroEvent(type="keyboard", action="down", key="a")], 1, 1.0,
                     lambda _cancelled, _error: done.set(), start_delay=0.05,
                     on_countdown=countdown.append)
        self.assertTrue(done.wait(1))
        self.assertEqual(countdown, [1, None])
        self.assertEqual(sum(call[0] == "press" for call in keyboard.calls), 1)

    def test_countdown_can_be_cancelled_before_events_start(self):
        keyboard = FakeKeyboard()
        player = MacroPlayer(keyboard, FakeMouse())
        done = threading.Event()
        result = []
        player.start([MacroEvent(type="keyboard", action="down", key="a")], 1, 1.0,
                     lambda cancelled, error: (result.append((cancelled, error)), done.set()),
                     start_delay=5)
        time.sleep(0.03)
        player.stop()
        self.assertTrue(done.wait(0.3))
        self.assertEqual(keyboard.calls, [])
        self.assertEqual(result, [(True, None)])

    def test_zero_second_countdown_starts_immediately(self):
        keyboard = FakeKeyboard()
        player = MacroPlayer(keyboard, FakeMouse())
        done = threading.Event()
        countdown = []
        player.start([MacroEvent(type="keyboard", action="down", key="a")], 1, 1.0,
                     lambda _cancelled, _error: done.set(), start_delay=0,
                     on_countdown=countdown.append)
        self.assertTrue(done.wait(1))
        self.assertEqual(countdown, [None])
        self.assertEqual(sum(call[0] == "press" for call in keyboard.calls), 1)

    def test_countdown_occurs_only_once_for_repeats(self):
        keyboard = FakeKeyboard()
        player = MacroPlayer(keyboard, FakeMouse())
        done = threading.Event()
        countdown = []
        player.start([MacroEvent(type="keyboard", action="down", key="a")], 3, 1.0,
                     lambda _cancelled, _error: done.set(), start_delay=0.03,
                     on_countdown=countdown.append)
        self.assertTrue(done.wait(1))
        self.assertEqual(countdown, [1, None])
        self.assertEqual(sum(call[0] == "press" for call in keyboard.calls), 3)


if __name__ == "__main__":
    unittest.main()
