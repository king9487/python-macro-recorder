from __future__ import annotations

import math
import queue
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from .event_dialog import edit_event
from .event_editor import EventEditError, EventEditorModel, format_delay
from .hotkeys import GlobalHotkeys
from .i18n import LANGUAGES, TRANSLATIONS
from .models import Macro, MacroEvent, MacroValidationError
from .player import MacroPlayer
from .recorder import MacroRecorder
from .storage import load_macro, save_macro


class MacroRecorderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.resizable(True, True)
        self.macro = Macro()
        self.editor = EventEditorModel(self.macro.events)
        self.current_path: Path | None = None
        if getattr(sys, "frozen", False):
            application_directory = Path(sys.executable).resolve().parent
        else:
            application_directory = Path(__file__).resolve().parent.parent
        self.script_directory = application_directory / "script"
        self.script_directory.mkdir(exist_ok=True)
        self.state = "Idle"
        self.messages: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.recorder = MacroRecorder(lambda count: self.messages.put(("count", count)))
        self.player = MacroPlayer()
        self.hotkeys = GlobalHotkeys(
            lambda: self.messages.put(("start_recording", None)),
            lambda: self.messages.put(("stop_recording", None)),
            lambda: self.messages.put(("stop_playback", None)),
        )

        self.name_var = tk.StringVar(value=self.macro.name)
        self.path_var = tk.StringVar(value="No file selected")
        self.repeat_var = tk.StringVar(value="1")
        self.speed_var = tk.StringVar(value="1.0")
        self.interval_var = tk.StringVar(value="0.0")
        self.start_delay_var = tk.StringVar(value="3.0")
        self.count_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value=self.state)
        self.saved_macro_var = tk.StringVar()
        self.language_var = tk.StringVar(value="繁體中文")
        self.countdown_remaining: int | None = None
        self._build()
        self._apply_language()
        self._refresh_saved_macros()
        self._update_controls()
        self.hotkeys.start()
        self.root.after(30, self._process_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.bind("<Control-s>", self._save_shortcut)
        self.root.bind("<Delete>", self._delete_shortcut)

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.rowconfigure(11, weight=1)
        self.name_label = ttk.Label(frame)
        self.name_label.grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.name_var, width=42).grid(row=0, column=1, columnspan=3, sticky="ew", pady=4)
        self.path_label = ttk.Label(frame)
        self.path_label.grid(row=1, column=0, sticky="w", pady=4)
        ttk.Label(frame, textvariable=self.path_var, width=48).grid(row=1, column=1, columnspan=3, sticky="w", pady=4)

        self.record_button = ttk.Button(frame, text="Record (F8)", command=self.start_recording)
        self.stop_record_button = ttk.Button(frame, text="Stop Recording (F9)", command=self.stop_recording)
        self.play_button = ttk.Button(frame, text="Play", command=self.start_playback)
        self.stop_play_button = ttk.Button(frame, text="Stop Playback (F10)", command=self.stop_playback)
        self.record_button.grid(row=2, column=0, sticky="ew", padx=3, pady=(12, 4))
        self.stop_record_button.grid(row=2, column=1, sticky="ew", padx=3, pady=(12, 4))
        self.play_button.grid(row=2, column=2, sticky="ew", padx=3, pady=(12, 4))
        self.stop_play_button.grid(row=2, column=3, sticky="ew", padx=3, pady=(12, 4))

        self.save_button = ttk.Button(frame, text="Save", command=self.save)
        self.load_button = ttk.Button(frame, text="Load Selected", command=self.load)
        self.delete_macro_button = ttk.Button(frame, command=self.delete_macro_selected)
        self.save_button.grid(row=3, column=0, sticky="ew", padx=3, pady=4)
        self.load_button.grid(row=3, column=1, columnspan=2, sticky="ew", padx=3, pady=4)
        self.delete_macro_button.grid(row=3, column=3, sticky="ew", padx=3, pady=4)

        self.saved_label = ttk.Label(frame)
        self.saved_label.grid(row=4, column=0, sticky="w", pady=(8, 4))
        self.saved_macro_combo = ttk.Combobox(frame, textvariable=self.saved_macro_var, state="readonly", width=39)
        self.saved_macro_combo.grid(row=4, column=1, columnspan=3, sticky="ew", pady=(8, 4))
        self.saved_macro_combo.bind("<<ComboboxSelected>>", lambda _event: self.load())

        self.repeat_label = ttk.Label(frame)
        self.repeat_label.grid(row=5, column=0, sticky="w", pady=(12, 4))
        self.repeat_entry = ttk.Spinbox(frame, from_=1, to=9999, textvariable=self.repeat_var, width=10)
        self.repeat_entry.grid(row=5, column=1, sticky="w", pady=(12, 4))
        self.speed_label = ttk.Label(frame)
        self.speed_label.grid(row=5, column=2, sticky="e", pady=(12, 4))
        self.speed_entry = ttk.Entry(frame, textvariable=self.speed_var, width=8)
        self.speed_entry.grid(row=5, column=3, sticky="w", pady=(12, 4))

        self.interval_label = ttk.Label(frame)
        self.interval_label.grid(row=6, column=0, sticky="w", pady=4)
        self.interval_entry = ttk.Entry(frame, textvariable=self.interval_var, width=10)
        self.interval_entry.grid(row=6, column=1, sticky="w", pady=4)

        self.start_delay_label = ttk.Label(frame)
        self.start_delay_label.grid(row=7, column=0, sticky="w", pady=4)
        self.start_delay_entry = ttk.Entry(frame, textvariable=self.start_delay_var, width=10)
        self.start_delay_entry.grid(row=7, column=1, sticky="w", pady=4)

        ttk.Separator(frame).grid(row=8, column=0, columnspan=4, sticky="ew", pady=10)
        self.events_label = ttk.Label(frame)
        self.events_label.grid(row=9, column=0, sticky="e")
        ttk.Label(frame, textvariable=self.count_var).grid(row=9, column=1, sticky="w")
        self.status_label = ttk.Label(frame)
        self.status_label.grid(row=9, column=2, sticky="e")
        ttk.Label(frame, textvariable=self.status_var).grid(row=9, column=3, sticky="w")

        self.language_label = ttk.Label(frame)
        self.language_label.grid(row=10, column=2, sticky="e", pady=(12, 0))
        self.language_combo = ttk.Combobox(frame, textvariable=self.language_var, values=list(LANGUAGES),
                                           state="readonly", width=12)
        self.language_combo.grid(row=10, column=3, sticky="w", pady=(12, 0))
        self.language_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_language())

        self.editor_frame = ttk.LabelFrame(frame, padding=8)
        self.editor_frame.grid(row=11, column=0, columnspan=4, sticky="nsew", pady=(12, 0))
        self.editor_frame.columnconfigure(0, weight=1)
        self.editor_frame.rowconfigure(0, weight=1)
        columns = ("number", "type", "action", "value", "delay")
        self.event_tree = ttk.Treeview(self.editor_frame, columns=columns, show="headings",
                                       selectmode="browse", height=12)
        self.event_tree.grid(row=0, column=0, sticky="nsew")
        self.event_tree.column("number", width=45, minwidth=40, anchor="center", stretch=False)
        self.event_tree.column("type", width=100, minwidth=80, anchor="w")
        self.event_tree.column("action", width=90, minwidth=70, anchor="w")
        self.event_tree.column("value", width=250, minwidth=150, anchor="w")
        self.event_tree.column("delay", width=90, minwidth=70, anchor="e", stretch=False)
        scrollbar = ttk.Scrollbar(self.editor_frame, orient="vertical", command=self.event_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.event_tree.configure(yscrollcommand=scrollbar.set)
        self.event_tree.bind("<<TreeviewSelect>>", lambda _event: self._update_editor_controls())
        self.event_tree.bind("<Double-1>", lambda _event: self.edit_selected_event())

        editor_buttons = ttk.Frame(self.editor_frame)
        editor_buttons.grid(row=1, column=0, columnspan=2, sticky="e", pady=(8, 0))
        self.edit_event_button = ttk.Button(editor_buttons, command=self.edit_selected_event)
        self.delete_event_button = ttk.Button(editor_buttons, command=self.delete_selected_event)
        self.move_up_button = ttk.Button(editor_buttons, command=self.move_selected_event_up)
        self.move_down_button = ttk.Button(editor_buttons, command=self.move_selected_event_down)
        self.edit_event_button.grid(row=0, column=0, padx=3)
        self.delete_event_button.grid(row=0, column=1, padx=3)
        self.move_up_button.grid(row=0, column=2, padx=3)
        self.move_down_button.grid(row=0, column=3, padx=3)

    def _text(self, key: str) -> str:
        language = LANGUAGES.get(self.language_var.get(), "en")
        return TRANSLATIONS[language][key]

    def _apply_language(self) -> None:
        self.root.title(self._text("title"))
        labels = {
            self.name_label: "macro_name", self.path_label: "current_file",
            self.saved_label: "saved_macros", self.repeat_label: "repeat_count",
            self.speed_label: "playback_speed", self.interval_label: "repeat_interval",
            self.start_delay_label: "start_delay",
            self.events_label: "events", self.status_label: "status", self.language_label: "language",
            self.record_button: "record", self.stop_record_button: "stop_recording",
            self.play_button: "play", self.stop_play_button: "stop_playback",
            self.save_button: "save", self.load_button: "load", self.delete_macro_button: "delete_macro_file",
            self.editor_frame: "event_editor", self.edit_event_button: "edit",
            self.delete_event_button: "delete", self.move_up_button: "move_up",
            self.move_down_button: "move_down",
        }
        for widget, key in labels.items():
            widget.configure(text=self._text(key))
        if self.current_path is None:
            self._update_path_display()
        headings = {"number": "number", "type": "type", "action": "action",
                    "value": "value", "delay": "delay"}
        for column, key in headings.items():
            self.event_tree.heading(column, text=self._text(key))
        self._refresh_event_table(self._selected_event_index())
        self._update_status()

    def _update_status(self) -> None:
        if self.state == "Playing" and self.countdown_remaining is not None:
            self.status_var.set(self._text("starting_in").format(seconds=self.countdown_remaining))
        elif self.state == "Playing":
            self.status_var.set(self._text("playing_now"))
        else:
            self.status_var.set(self._text(self.state))

    def _set_state(self, state: str) -> None:
        self.state = state
        if state != "Playing":
            self.countdown_remaining = None
        self._update_status()
        self._update_controls()

    def _update_controls(self) -> None:
        idle = self.state in {"Idle", "Stopped"}
        recording = self.state == "Recording"
        playing = self.state == "Playing"
        self.record_button.configure(state="normal" if idle else "disabled")
        self.stop_record_button.configure(state="normal" if recording else "disabled")
        self.play_button.configure(state="normal" if idle and self.macro.events else "disabled")
        self.stop_play_button.configure(state="normal" if playing else "disabled")
        for widget in (self.save_button, self.load_button, self.delete_macro_button,
                       self.repeat_entry, self.speed_entry,
                       self.interval_entry, self.start_delay_entry):
            widget.configure(state="normal" if idle else "disabled")
        if idle and not self.saved_macro_var.get():
            self.load_button.configure(state="disabled")
            self.delete_macro_button.configure(state="disabled")
        self.saved_macro_combo.configure(state="readonly" if idle else "disabled")
        self._update_editor_controls()

    def _selected_event_index(self) -> int | None:
        selection = self.event_tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    def _update_editor_controls(self) -> None:
        idle = self.state in {"Idle", "Stopped"}
        index = self._selected_event_index()
        valid = idle and index is not None and 0 <= index < len(self.editor.events)
        self.edit_event_button.configure(state="normal" if valid else "disabled")
        self.delete_event_button.configure(state="normal" if valid else "disabled")
        self.move_up_button.configure(state="normal" if valid and index > 0 else "disabled")
        self.move_down_button.configure(
            state="normal" if valid and index < len(self.editor.events) - 1 else "disabled"
        )

    def _refresh_event_table(self, selected: int | None = None) -> None:
        self.event_tree.delete(*self.event_tree.get_children())
        for index, event in enumerate(self.editor.events):
            self.event_tree.insert("", "end", iid=str(index), values=self._event_row(index, event))
        self.count_var.set(str(len(self.editor.events)))
        if selected is not None and 0 <= selected < len(self.editor.events):
            item = str(selected)
            self.event_tree.selection_set(item)
            self.event_tree.focus(item)
            self.event_tree.see(item)
        self._update_editor_controls()

    def _event_row(self, index: int, event: MacroEvent) -> tuple[str, str, str, str, str]:
        event_type = self._text("type_keyboard") if event.type == "keyboard" else self._text("type_mouse")
        action = self._text(f"action_{event.action}")
        if event.type == "keyboard":
            value = event.key or ""
        elif event.action == "move":
            value = f"{event.x}, {event.y}"
        elif event.action in {"down", "up"}:
            button = self._text(f"button_{event.button}")
            value = f"{button} @ {event.x}, {event.y}"
        else:
            value = f"{event.dx}, {event.dy}"
        return str(index + 1), event_type, action, value, format_delay(event.delay)

    def edit_selected_event(self) -> None:
        if self.state not in {"Idle", "Stopped"}:
            return
        index = self._selected_event_index()
        if index is None:
            return
        values = edit_event(self.root, self.editor.events[index], self._text)
        if values is None:
            return
        try:
            self.editor.edit(index, values)
        except EventEditError as exc:
            message = self._event_edit_error(exc)
            messagebox.showerror(self._text("validation_error"), message, parent=self.root)
            return
        self._after_editor_change(index)

    def delete_selected_event(self) -> None:
        if self.state not in {"Idle", "Stopped"}:
            return
        index = self._selected_event_index()
        if index is None:
            return
        question = self._text("delete_event_question").format(number=index + 1)
        if not messagebox.askyesno(self._text("delete_event"), question, parent=self.root):
            return
        selected = self.editor.delete(index)
        self._after_editor_change(selected)

    def move_selected_event_up(self) -> None:
        index = self._selected_event_index()
        if self.state in {"Idle", "Stopped"} and index is not None:
            self._after_editor_change(self.editor.move_up(index))

    def move_selected_event_down(self) -> None:
        index = self._selected_event_index()
        if self.state in {"Idle", "Stopped"} and index is not None:
            self._after_editor_change(self.editor.move_down(index))

    def _after_editor_change(self, selected: int | None) -> None:
        self._refresh_event_table(selected)
        self._update_path_display()
        self._update_controls()

    def _event_edit_error(self, error: EventEditError) -> str:
        if error.code == "invalid_integer" and error.field:
            return self._text("validation_integer").format(field=self._text(error.field))
        return self._text(f"validation_{error.code}")

    def _update_path_display(self) -> None:
        path = str(self.current_path) if self.current_path else self._text("no_file")
        self.path_var.set(f"{path} *" if self.editor.dirty else path)

    def _confirm_discard_changes(self) -> bool:
        if not self.editor.dirty:
            return True
        return messagebox.askyesno(
            self._text("unsaved_changes"), self._text("discard_changes_question"), parent=self.root
        )

    def start_recording(self) -> None:
        if self.state not in {"Idle", "Stopped"}:
            return
        if not self._confirm_discard_changes():
            return
        try:
            self.recorder.start()
        except Exception as exc:
            messagebox.showerror(self._text("recording_error"), str(exc), parent=self.root)
            return
        self.macro.events = []
        self.editor.load(self.macro.events)
        self._refresh_event_table()
        self._update_path_display()
        self._set_state("Recording")
        self.root.after_idle(self.root.iconify)

    def stop_recording(self) -> None:
        if self.state != "Recording":
            return
        self.macro.events = self.recorder.stop()
        self.editor.load(self.macro.events, dirty=True)
        self._refresh_event_table(0 if self.macro.events else None)
        self._update_path_display()
        self._set_state("Stopped")
        self._restore_window()

    def _restore_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(150, lambda: self.root.attributes("-topmost", False))
        self.root.after_idle(self.root.focus_force)

    def _playback_settings(self) -> tuple[int, float, float, float]:
        try:
            repeat = int(self.repeat_var.get())
            speed = float(self.speed_var.get().lower().rstrip("x"))
            interval = float(self.interval_var.get())
            start_delay = float(self.start_delay_var.get())
        except ValueError as exc:
            raise ValueError(self._text("settings_numbers")) from exc
        if not 1 <= repeat <= 9999:
            raise ValueError(self._text("repeat_range"))
        if not 0.1 <= speed <= 10.0:
            raise ValueError(self._text("speed_range"))
        if not 0 <= interval <= 86400:
            raise ValueError(self._text("interval_range"))
        if not 0 <= start_delay <= 30:
            raise ValueError(self._text("start_delay_range"))
        return repeat, speed, interval, start_delay

    def start_playback(self) -> None:
        if self.state not in {"Idle", "Stopped"}:
            return
        try:
            repeat, speed, interval, start_delay = self._playback_settings()
            self.player.start(self.macro.events, repeat, speed,
                              lambda cancelled, error: self.messages.put(("playback_finished", (cancelled, error))),
                              repeat_interval=interval, start_delay=start_delay,
                              on_countdown=lambda value: self.messages.put(("countdown", value)))
        except Exception as exc:
            messagebox.showerror(self._text("playback_error"), str(exc), parent=self.root)
            return
        self.countdown_remaining = max(1, math.ceil(start_delay)) if start_delay > 0 else None
        self._set_state("Playing")
        self.root.after_idle(self.root.iconify)

    def stop_playback(self) -> None:
        if self.state == "Playing":
            self.player.stop()

    def save(self) -> None:
        try:
            repeat, _, interval, _ = self._playback_settings()
        except ValueError as exc:
            messagebox.showerror(self._text("invalid_settings"), str(exc), parent=self.root)
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror(self._text("invalid_name"), self._text("enter_name"), parent=self.root)
            return
        if any(character in name for character in '<>:"/\\|?*') or name in {".", ".."}:
            messagebox.showerror(self._text("invalid_name"), self._text("bad_name_chars"), parent=self.root)
            return
        path = self.script_directory / f"{name}.json"
        if path.exists() and path != self.current_path:
            question = self._text("replace_question").format(filename=f"{name}.json")
            if not messagebox.askyesno(self._text("replace_macro"), question, parent=self.root):
                return
        self.macro.name = name
        self.macro.repeat = repeat
        self.macro.repeat_interval = interval
        try:
            save_macro(self.macro, path)
        except MacroValidationError as exc:
            messagebox.showerror(self._text("save_error"), str(exc), parent=self.root)
            return
        self.current_path = path
        self.editor.mark_saved()
        self._update_path_display()
        self._refresh_saved_macros(path.name)
        self._set_state("Idle")

    def load(self) -> None:
        filename = self.saved_macro_var.get()
        if not filename:
            messagebox.showinfo(self._text("load_macro"), self._text("no_macros"), parent=self.root)
            return
        if not self._confirm_discard_changes():
            self.saved_macro_var.set(self.current_path.name if self.current_path else "")
            self._update_controls()
            return
        path = self.script_directory / filename
        try:
            macro = load_macro(path)
        except MacroValidationError as exc:
            messagebox.showerror(self._text("invalid_macro"), str(exc), parent=self.root)
            self.saved_macro_var.set(self.current_path.name if self.current_path else "")
            self._update_controls()
            return
        self.macro = macro
        self.editor.load(macro.events)
        self.current_path = Path(path)
        self.name_var.set(macro.name)
        self.repeat_var.set(str(macro.repeat))
        self.interval_var.set(str(macro.repeat_interval))
        self._update_path_display()
        self._refresh_event_table(0 if macro.events else None)
        self._set_state("Idle")

    def delete_macro_selected(self) -> None:
        if self.state not in {"Idle", "Stopped"}:
            return
        filename = self.saved_macro_var.get()
        if not filename:
            messagebox.showinfo(self._text("delete_macro"), self._text("no_macros"), parent=self.root)
            return
        question = self._text("delete_question").format(filename=filename)
        if not messagebox.askyesno(self._text("delete_macro"), question, parent=self.root):
            return
        path = self.script_directory / filename
        try:
            path.unlink()
        except OSError as exc:
            messagebox.showerror(self._text("delete_error"), str(exc), parent=self.root)
            return
        if self.current_path == path:
            self.current_path = None
            self._update_path_display()
        self.saved_macro_var.set("")
        self._refresh_saved_macros()
        self._update_controls()

    def _save_shortcut(self, _event: tk.Event) -> str | None:
        if self.state in {"Idle", "Stopped"}:
            self.save()
            return "break"
        return None

    def _delete_shortcut(self, event: tk.Event) -> str | None:
        if event.widget is self.event_tree and self.state in {"Idle", "Stopped"}:
            self.delete_selected_event()
            return "break"
        return None

    def _refresh_saved_macros(self, selected: str | None = None) -> None:
        filenames = sorted((path.name for path in self.script_directory.glob("*.json")), key=str.casefold)
        self.saved_macro_combo.configure(values=filenames)
        if selected in filenames:
            self.saved_macro_var.set(selected)
        elif self.saved_macro_var.get() not in filenames:
            self.saved_macro_var.set(filenames[0] if filenames else "")

    def _process_messages(self) -> None:
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "count":
                    self.count_var.set(str(payload))
                elif kind == "start_recording":
                    self.start_recording()
                elif kind == "stop_recording":
                    self.stop_recording()
                elif kind == "stop_playback":
                    self.stop_playback()
                elif kind == "countdown" and self.state == "Playing":
                    self.countdown_remaining = payload
                    self._update_status()
                elif kind == "playback_finished":
                    cancelled, error = payload
                    self._set_state("Stopped" if cancelled else "Idle")
                    self._restore_window()
                    if error:
                        messagebox.showerror(self._text("playback_error"), error, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(30, self._process_messages)

    def _close(self) -> None:
        if self.state == "Recording":
            self.macro.events = self.recorder.stop()
            self.editor.load(self.macro.events, dirty=True)
            self._refresh_event_table()
            self._set_state("Stopped")
            self._restore_window()
        if not self._confirm_discard_changes():
            return
        self.player.stop()
        self.hotkeys.stop()
        self.root.destroy()


def run() -> None:
    root = tk.Tk()
    MacroRecorderApp(root)
    root.mainloop()
