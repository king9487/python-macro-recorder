from __future__ import annotations

from collections.abc import Callable

from pynput import keyboard


class GlobalHotkeys:
    def __init__(self, on_record: Callable[[], None], on_stop_recording: Callable[[], None],
                 on_stop_playback: Callable[[], None]) -> None:
        callbacks = {keyboard.Key.f8: on_record, keyboard.Key.f9: on_stop_recording,
                     keyboard.Key.f10: on_stop_playback}
        self._listener = keyboard.Listener(on_press=lambda key: callbacks.get(key, lambda: None)())

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
