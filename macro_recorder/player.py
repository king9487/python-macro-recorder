from __future__ import annotations

import math
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
    if special is not None:
        return special
    if len(value) != 1:
        raise ValueError(f"Invalid keyboard key: {value!r}")
    return keyboard.KeyCode.from_char(value)


class MacroPlayer:
    def __init__(self, keyboard_controller: keyboard.Controller | None = None,
                 mouse_controller: mouse.Controller | None = None) -> None:
        self._keyboard = keyboard_controller or keyboard.Controller()
        self._mouse = mouse_controller or mouse.Controller()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._input_lock = threading.Lock()
        self._pressed_keys: set[keyboard.Key | keyboard.KeyCode] = set()
        self._pressed_buttons: set[mouse.Button] = set()

    @property
    def playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, events: list[MacroEvent], repeat: int, speed: float,
              on_finished: Callable[[bool, str | None], None], repeat_interval: float = 0.0,
              start_delay: float = 0.0,
              on_countdown: Callable[[int | None], None] | None = None) -> None:
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
        if not 0 <= start_delay <= 30:
            raise ValueError("Start delay must be from 0 to 30 seconds.")
        self._stop_event.clear()
        cleanup_errors = self.release_all_inputs()
        if cleanup_errors:
            raise RuntimeError("; ".join(cleanup_errors))
        self._thread = threading.Thread(target=self._run,
                                        args=(list(events), repeat, speed, repeat_interval, start_delay,
                                              on_countdown, on_finished),
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

    def release_all_inputs(self) -> list[str]:
        """Release only inputs successfully pressed and still tracked by this player."""
        errors: list[str] = []
        with self._input_lock:
            keys = list(self._pressed_keys)
            buttons = list(self._pressed_buttons)
            self._pressed_keys.clear()
            self._pressed_buttons.clear()
        for key in keys:
            try:
                self._keyboard.release(key)
            except Exception as exc:
                errors.append(f"Could not release keyboard key {key!r}: {exc}")
                with self._input_lock:
                    self._pressed_keys.add(key)
        for button in buttons:
            try:
                self._mouse.release(button)
            except Exception as exc:
                errors.append(f"Could not release mouse button {button!r}: {exc}")
                with self._input_lock:
                    self._pressed_buttons.add(button)
        return errors

    def _run_countdown(self, seconds: float,
                       on_countdown: Callable[[int | None], None] | None) -> bool:
        deadline = time.monotonic() + seconds
        last_value: int | None = None
        while not self._stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if on_countdown:
                    on_countdown(None)
                return True
            value = max(1, math.ceil(remaining))
            if on_countdown and value != last_value:
                on_countdown(value)
                last_value = value
            self._stop_event.wait(min(remaining, 0.02))
        return False

    def _run(self, events: list[MacroEvent], repeat: int, speed: float, repeat_interval: float,
             start_delay: float, on_countdown: Callable[[int | None], None] | None,
             on_finished: Callable[[bool, str | None], None]) -> None:
        error: str | None = None
        try:
            if not self._run_countdown(start_delay, on_countdown):
                return
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
            cleanup_errors = self.release_all_inputs()
            if cleanup_errors:
                cleanup_error = "; ".join(cleanup_errors)
                error = f"{error}; {cleanup_error}" if error else cleanup_error
            on_finished(self._stop_event.is_set(), error)

    def _dispatch(self, event: MacroEvent) -> None:
        if event.type == "keyboard":
            key = decode_key(event.key or "")
            if event.action == "down":
                self._keyboard.press(key)
                with self._input_lock:
                    self._pressed_keys.add(key)
            else:
                self._keyboard.release(key)
                with self._input_lock:
                    self._pressed_keys.discard(key)
            return
        if event.action == "move":
            self._mouse.position = (event.x, event.y)
        elif event.action in {"down", "up"}:
            button = getattr(mouse.Button, event.button or "")
            self._mouse.position = (event.x, event.y)
            if event.action == "down":
                self._mouse.press(button)
                with self._input_lock:
                    self._pressed_buttons.add(button)
            else:
                self._mouse.release(button)
                with self._input_lock:
                    self._pressed_buttons.discard(button)
        else:
            self._mouse.scroll(event.dx, event.dy)
