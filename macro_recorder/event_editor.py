from __future__ import annotations

import math
from collections.abc import Mapping

from .models import MacroEvent
from .player import decode_key


class EventEditError(ValueError):
    def __init__(self, code: str, field: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.field = field


class EventEditorModel:
    """Mutates one macro event list in place and tracks unsaved editor changes."""

    def __init__(self, events: list[MacroEvent] | None = None) -> None:
        self.events = events if events is not None else []
        self.dirty = False

    def load(self, events: list[MacroEvent], *, dirty: bool = False) -> None:
        self.events = events
        self.dirty = dirty

    def mark_saved(self) -> None:
        self.dirty = False

    def edit(self, index: int, values: Mapping[str, str]) -> MacroEvent:
        event = self._event_at(index)
        delay = self._parse_delay(values.get("delay", ""))
        if event.type == "keyboard":
            action = values.get("action", "")
            if action not in {"down", "up"}:
                raise EventEditError("invalid_action")
            key = values.get("key", "")
            if not key:
                raise EventEditError("invalid_key")
            try:
                decode_key(key)
            except (TypeError, ValueError):
                raise EventEditError("invalid_key") from None
            replacement = MacroEvent(type="keyboard", action=action, key=key, delay=delay)
        elif event.action == "move":
            replacement = MacroEvent(type="mouse", action="move",
                                     x=self._parse_int(values.get("x", ""), "x"),
                                     y=self._parse_int(values.get("y", ""), "y"), delay=delay)
        elif event.action in {"down", "up"}:
            action = values.get("action", "")
            if action not in {"down", "up"}:
                raise EventEditError("invalid_action")
            button = values.get("button", "")
            if button not in {"left", "middle", "right"}:
                raise EventEditError("invalid_button")
            replacement = MacroEvent(type="mouse", action=action, button=button,
                                     x=self._parse_int(values.get("x", ""), "x"),
                                     y=self._parse_int(values.get("y", ""), "y"), delay=delay)
        else:
            replacement = MacroEvent(type="mouse", action="scroll",
                                     dx=self._parse_int(values.get("dx", ""), "dx"),
                                     dy=self._parse_int(values.get("dy", ""), "dy"), delay=delay)
        self.events[index] = replacement
        self.dirty = True
        return replacement

    def delete(self, index: int) -> int | None:
        self._event_at(index)
        del self.events[index]
        self.dirty = True
        if not self.events:
            return None
        return min(index, len(self.events) - 1)

    def move_up(self, index: int) -> int:
        self._event_at(index)
        if index == 0:
            return index
        self.events[index - 1], self.events[index] = self.events[index], self.events[index - 1]
        self.dirty = True
        return index - 1

    def move_down(self, index: int) -> int:
        self._event_at(index)
        if index == len(self.events) - 1:
            return index
        self.events[index], self.events[index + 1] = self.events[index + 1], self.events[index]
        self.dirty = True
        return index + 1

    def _event_at(self, index: int) -> MacroEvent:
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self.events):
            raise EventEditError("invalid_selection")
        return self.events[index]

    @staticmethod
    def _parse_delay(value: str) -> float:
        try:
            delay = float(value)
        except (TypeError, ValueError):
            raise EventEditError("invalid_delay") from None
        if not math.isfinite(delay) or delay < 0:
            raise EventEditError("invalid_delay")
        return delay

    @staticmethod
    def _parse_int(value: str, field: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise EventEditError("invalid_integer", field) from None


def format_delay(delay: float) -> str:
    value = f"{delay:.6f}".rstrip("0").rstrip(".")
    whole, separator, fraction = value.partition(".")
    if not separator:
        return f"{whole}.000"
    return f"{whole}.{fraction.ljust(3, '0')}"
