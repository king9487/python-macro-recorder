from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable

from pynput import keyboard, mouse

from .models import MacroEvent


EMERGENCY_KEYS = {keyboard.Key.f8, keyboard.Key.f9, keyboard.Key.f10}


def encode_key(key: keyboard.Key | keyboard.KeyCode) -> str:
    if isinstance(key, keyboard.KeyCode):
        if key.char is not None:
            return key.char
        if key.vk is not None:
            return f"vk:{key.vk}"
    name = getattr(key, "name", None)
    return name if name else str(key)


class MacroRecorder:
    def __init__(self, on_event: Callable[[int], None] | None = None) -> None:
        self._on_event = on_event
        self._events: list[MacroEvent] = []
        self._lock = threading.Lock()
        self._keyboard_listener: keyboard.Listener | None = None
        self._mouse_listener: mouse.Listener | None = None
        self._last_event_time = 0.0
        self._last_move_time = 0.0
        self._last_move_position: tuple[int, int] | None = None
        self._recording = False

    @property
    def recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        if self._recording:
            raise RuntimeError("Recording is already active.")
        with self._lock:
            self._events = []
            self._last_event_time = time.monotonic()
            self._last_move_time = 0.0
            self._last_move_position = None
            self._recording = True
        self._keyboard_listener = keyboard.Listener(on_press=self._on_key_down, on_release=self._on_key_up)
        self._mouse_listener = mouse.Listener(on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll)
        self._keyboard_listener.start()
        self._mouse_listener.start()

    def stop(self) -> list[MacroEvent]:
        with self._lock:
            self._recording = False
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        with self._lock:
            return list(self._events)

    def _append(self, event: MacroEvent, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        with self._lock:
            if not self._recording:
                return
            event.delay = max(0.0, current - self._last_event_time)
            self._last_event_time = current
            self._events.append(event)
            count = len(self._events)
        if self._on_event:
            self._on_event(count)

    def _on_key_down(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if key not in EMERGENCY_KEYS:
            self._append(MacroEvent(type="keyboard", action="down", key=encode_key(key)))

    def _on_key_up(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if key not in EMERGENCY_KEYS:
            self._append(MacroEvent(type="keyboard", action="up", key=encode_key(key)))

    def _on_move(self, x: int, y: int) -> None:
        now = time.monotonic()
        position = (int(x), int(y))
        previous = self._last_move_position
        elapsed = now - self._last_move_time
        distance = math.dist(position, previous) if previous else float("inf")
        if elapsed >= 0.02 or distance >= 5.0:
            self._last_move_time = now
            self._last_move_position = position
            self._append(MacroEvent(type="mouse", action="move", x=position[0], y=position[1]), now)

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        name = getattr(button, "name", None)
        if name in {"left", "middle", "right"}:
            self._append(MacroEvent(type="mouse", action="down" if pressed else "up",
                                    button=name, x=int(x), y=int(y)))

    def _on_scroll(self, _x: int, _y: int, dx: int, dy: int) -> None:
        self._append(MacroEvent(type="mouse", action="scroll", dx=int(dx), dy=int(dy)))
