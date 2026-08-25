from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from .event_editor import format_delay
from .models import MacroEvent


class EditEventDialog:
    def __init__(self, parent: tk.Misc, event: MacroEvent, text: Callable[[str], str]) -> None:
        self._text = text
        self._event = event
        self.result: dict[str, str] | None = None
        self.window = tk.Toplevel(parent)
        self.window.title(text("edit_event"))
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.variables: dict[str, tk.StringVar] = {}
        self._action_display = {text("action_down"): "down", text("action_up"): "up"}
        self._button_display = {
            text("button_left"): "left", text("button_middle"): "middle", text("button_right"): "right"
        }
        self._build()
        self.window.bind("<Return>", lambda _event: self._save())
        self.window.bind("<Escape>", lambda _event: self._cancel())
        self.window.grab_set()
        self.window.wait_visibility()
        self.window.focus_force()
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, padding=16)
        frame.grid(sticky="nsew")
        row = 0
        if self._event.type == "keyboard":
            row = self._add_choice(frame, row, "action", "action", self._action_display,
                                   self._event.action)
            row = self._add_entry(frame, row, "key", "key", self._event.key or "")
        elif self._event.action == "move":
            row = self._add_entry(frame, row, "x", "x", str(self._event.x))
            row = self._add_entry(frame, row, "y", "y", str(self._event.y))
        elif self._event.action in {"down", "up"}:
            row = self._add_choice(frame, row, "action", "action", self._action_display,
                                   self._event.action)
            row = self._add_choice(frame, row, "button", "button", self._button_display,
                                   self._event.button or "left")
            row = self._add_entry(frame, row, "x", "x", str(self._event.x))
            row = self._add_entry(frame, row, "y", "y", str(self._event.y))
        else:
            row = self._add_entry(frame, row, "dx", "dx", str(self._event.dx))
            row = self._add_entry(frame, row, "dy", "dy", str(self._event.dy))
        row = self._add_entry(frame, row, "delay", "delay", format_delay(self._event.delay))

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text=self._text("save_changes"), command=self._save).grid(row=0, column=0, padx=4)
        ttk.Button(buttons, text=self._text("cancel"), command=self._cancel).grid(row=0, column=1)

    def _add_entry(self, frame: ttk.Frame, row: int, name: str, label: str, value: str) -> int:
        variable = tk.StringVar(value=value)
        self.variables[name] = variable
        ttk.Label(frame, text=self._text(label)).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        entry = ttk.Entry(frame, textvariable=variable, width=28)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        if row == 0:
            entry.focus_set()
        return row + 1

    def _add_choice(self, frame: ttk.Frame, row: int, name: str, label: str,
                    choices: dict[str, str], selected: str) -> int:
        display = next((shown for shown, value in choices.items() if value == selected), next(iter(choices)))
        variable = tk.StringVar(value=display)
        self.variables[name] = variable
        ttk.Label(frame, text=self._text(label)).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        combo = ttk.Combobox(frame, textvariable=variable, values=list(choices), state="readonly", width=25)
        combo.grid(row=row, column=1, sticky="ew", pady=4)
        if row == 0:
            combo.focus_set()
        return row + 1

    def _save(self) -> None:
        result = {name: variable.get().strip() for name, variable in self.variables.items()}
        if "action" in result:
            result["action"] = self._action_display.get(result["action"], "")
        if "button" in result:
            result["button"] = self._button_display.get(result["button"], "")
        self.result = result
        self.window.destroy()

    def _cancel(self) -> None:
        self.window.destroy()


def edit_event(parent: tk.Misc, event: MacroEvent,
               text: Callable[[str], str]) -> dict[str, str] | None:
    return EditEventDialog(parent, event, text).result
