from __future__ import annotations

import threading
import time
from collections.abc import Callable

from pynput import keyboard, mouse

from .models import MacroEvent


def decode_key(value: str) -> keyboard.Key | keyboard.KeyCode:
    if value.startswith("vk:"):
        try:
            return keyboard.KeyCode.from_vk(int(value[3:]))
        except ValueError as exc:
            raise ValueError(f"Invalid virtual key: {value!r}") from exc
    special = getattr(keyboard.Key, value, None)
    return special if special is not None else keyboard.KeyCode.from_char(value)


class MacroPlayer:
    def __init__(self, keyboard_controller: keyboard.Controller | None = None,
                 mouse_controller: mouse.Controller | None = None) -> None:
        self._keyboard = keyboard_controller or keyboard.Controller()
        self._mouse = mouse_controller or mouse.Controller()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, events: list[MacroEvent], repeat: int, speed: float,
              on_finished: Callable[[bool, str | None], None], repeat_interval: float = 0.0) -> None:
        if self.playing:
            raise RuntimeError("Playback is already active.")
        if not events:
            raise ValueError("There are no events to play.")
        if not 1 <= repeat <= 9999:
            raise ValueError("Repeat count must be from 1 to 9999.")
        if not 0.1 <= speed <= 10.0:
            raise ValueError("Playback speed must be from 0.1 to 10.0.")
        if not 0 <= repeat_interval <= 86400:
            raise ValueError("Repeat interval must be from 0 to 86400 seconds.")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run,
                                        args=(list(events), repeat, speed, repeat_interval, on_finished),
                                        name="macro-playback", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def interruptible_sleep(self, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        while not self._stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            self._stop_event.wait(min(remaining, 0.02))
        return False

    def _run(self, events: list[MacroEvent], repeat: int, speed: float, repeat_interval: float,
             on_finished: Callable[[bool, str | None], None]) -> None:
        error: str | None = None
        try:
            for repetition in range(repeat):
                for event in events:
                    if not self.interruptible_sleep(event.delay / speed):
                        return
                    self._dispatch(event)
                    if self._stop_event.is_set():
                        return
                if repetition < repeat - 1 and not self.interruptible_sleep(repeat_interval):
                    return
        except Exception as exc:
            error = str(exc)
        finally:
            on_finished(self._stop_event.is_set(), error)

    def _dispatch(self, event: MacroEvent) -> None:
        if event.type == "keyboard":
            key = decode_key(event.key or "")
            (self._keyboard.press if event.action == "down" else self._keyboard.release)(key)
            return
        if event.action == "move":
            self._mouse.position = (event.x, event.y)
        elif event.action in {"down", "up"}:
            button = getattr(mouse.Button, event.button or "")
            self._mouse.position = (event.x, event.y)
            (self._mouse.press if event.action == "down" else self._mouse.release)(button)
        else:
            self._mouse.scroll(event.dx, event.dy)
