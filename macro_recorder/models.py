from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class MacroValidationError(ValueError):
    """Raised when macro data is unsafe or malformed."""


@dataclass(slots=True)
class MacroEvent:
    type: str
    action: str
    delay: float = 0.0
    key: str | None = None
    x: int | None = None
    y: int | None = None
    button: str | None = None
    dx: int = 0
    dy: int = 0

    @classmethod
    def from_dict(cls, data: Any) -> "MacroEvent":
        if not isinstance(data, dict):
            raise MacroValidationError("Each event must be a JSON object.")
        event_type = data.get("type")
        action = data.get("action")
        delay = data.get("delay", 0.0)
        if event_type not in {"keyboard", "mouse"}:
            raise MacroValidationError(f"Unsupported event type: {event_type!r}.")
        valid_actions = {"down", "up"} if event_type == "keyboard" else {"move", "down", "up", "scroll"}
        if action not in valid_actions:
            raise MacroValidationError(f"Unsupported {event_type} action: {action!r}.")
        if isinstance(delay, bool) or not isinstance(delay, (int, float)) or delay < 0:
            raise MacroValidationError("Event delay must be a non-negative number.")

        kwargs: dict[str, Any] = {"type": event_type, "action": action, "delay": float(delay)}
        if event_type == "keyboard":
            key = data.get("key")
            if not isinstance(key, str) or not key:
                raise MacroValidationError("Keyboard events require a non-empty 'key'.")
            kwargs["key"] = key
        elif action in {"move", "down", "up"}:
            for coordinate in ("x", "y"):
                value = data.get(coordinate)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise MacroValidationError(f"Mouse {action} events require numeric '{coordinate}'.")
                kwargs[coordinate] = int(value)
            if action in {"down", "up"}:
                button = data.get("button")
                if button not in {"left", "middle", "right"}:
                    raise MacroValidationError("Mouse button must be left, middle, or right.")
                kwargs["button"] = button
        else:
            for axis in ("dx", "dy"):
                value = data.get(axis, 0)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise MacroValidationError(f"Mouse scroll '{axis}' must be numeric.")
                kwargs[axis] = int(value)
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type, "action": self.action, "delay": round(self.delay, 6)}
        if self.type == "keyboard":
            result["key"] = self.key
        elif self.action == "move":
            result.update(x=self.x, y=self.y)
        elif self.action in {"down", "up"}:
            result.update(button=self.button, x=self.x, y=self.y)
        else:
            result.update(dx=self.dx, dy=self.dy)
        return result


@dataclass(slots=True)
class Macro:
    name: str = "Untitled Macro"
    repeat: int = 1
    repeat_interval: float = 0.0
    events: list[MacroEvent] = field(default_factory=list)
    version: int = 1

    @classmethod
    def from_dict(cls, data: Any) -> "Macro":
        if not isinstance(data, dict):
            raise MacroValidationError("The macro file must contain a JSON object.")
        version = data.get("version", 1)
        if version != 1:
            raise MacroValidationError(f"Unsupported macro version: {version!r}.")
        name = data.get("name", "Untitled Macro")
        if not isinstance(name, str):
            raise MacroValidationError("Macro name must be text.")
        repeat = data.get("repeat", 1)
        if isinstance(repeat, bool) or not isinstance(repeat, int) or not 1 <= repeat <= 9999:
            raise MacroValidationError("Repeat count must be an integer from 1 to 9999.")
        repeat_interval = data.get("repeat_interval", 0.0)
        if (isinstance(repeat_interval, bool) or not isinstance(repeat_interval, (int, float))
                or not 0 <= repeat_interval <= 86400):
            raise MacroValidationError("Repeat interval must be a number from 0 to 86400 seconds.")
        events = data.get("events")
        if not isinstance(events, list):
            raise MacroValidationError("The macro must have an 'events' array.")
        return cls(name=name.strip() or "Untitled Macro", repeat=repeat, repeat_interval=float(repeat_interval),
                   events=[MacroEvent.from_dict(item) for item in events], version=version)

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "name": self.name, "repeat": self.repeat,
                "repeat_interval": self.repeat_interval,
                "events": [event.to_dict() for event in self.events]}
