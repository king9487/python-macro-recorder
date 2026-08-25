from __future__ import annotations

import queue
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from .hotkeys import GlobalHotkeys
from .i18n import LANGUAGES, TRANSLATIONS
from .models import Macro, MacroValidationError
from .player import MacroPlayer
from .recorder import MacroRecorder
from .storage import load_macro, save_macro


class MacroRecorderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.resizable(False, False)
        self.macro = Macro()
        self.current_path: Path | None = None
        self.script_directory = Path(__file__).resolve().parent.parent / "script"
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
        self.count_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value=self.state)
        self.saved_macro_var = tk.StringVar()
        self.language_var = tk.StringVar(value="繁體中文")
        self._build()
        self._apply_language()
        self._refresh_saved_macros()
        self._update_controls()
        self.hotkeys.start()
        self.root.after(30, self._process_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(sticky="nsew")
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
        self.delete_button = ttk.Button(frame, command=self.delete_selected)
        self.save_button.grid(row=3, column=0, sticky="ew", padx=3, pady=4)
        self.load_button.grid(row=3, column=1, columnspan=2, sticky="ew", padx=3, pady=4)
        self.delete_button.grid(row=3, column=3, sticky="ew", padx=3, pady=4)

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

        ttk.Separator(frame).grid(row=7, column=0, columnspan=4, sticky="ew", pady=10)
        self.events_label = ttk.Label(frame)
        self.events_label.grid(row=8, column=0, sticky="e")
        ttk.Label(frame, textvariable=self.count_var).grid(row=8, column=1, sticky="w")
        self.status_label = ttk.Label(frame)
        self.status_label.grid(row=8, column=2, sticky="e")
        ttk.Label(frame, textvariable=self.status_var).grid(row=8, column=3, sticky="w")

        self.language_label = ttk.Label(frame)
        self.language_label.grid(row=9, column=2, sticky="e", pady=(12, 0))
        self.language_combo = ttk.Combobox(frame, textvariable=self.language_var, values=list(LANGUAGES),
                                           state="readonly", width=12)
        self.language_combo.grid(row=9, column=3, sticky="w", pady=(12, 0))
        self.language_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_language())

    def _text(self, key: str) -> str:
        language = LANGUAGES.get(self.language_var.get(), "en")
        return TRANSLATIONS[language][key]

    def _apply_language(self) -> None:
        self.root.title(self._text("title"))
        labels = {
            self.name_label: "macro_name", self.path_label: "current_file",
            self.saved_label: "saved_macros", self.repeat_label: "repeat_count",
            self.speed_label: "playback_speed", self.interval_label: "repeat_interval",
            self.events_label: "events", self.status_label: "status", self.language_label: "language",
            self.record_button: "record", self.stop_record_button: "stop_recording",
            self.play_button: "play", self.stop_play_button: "stop_playback",
            self.save_button: "save", self.load_button: "load", self.delete_button: "delete",
        }
        for widget, key in labels.items():
            widget.configure(text=self._text(key))
        if self.current_path is None:
            self.path_var.set(self._text("no_file"))
        self.status_var.set(self._text(self.state))

    def _set_state(self, state: str) -> None:
        self.state = state
        self.status_var.set(self._text(state))
        self._update_controls()

    def _update_controls(self) -> None:
        idle = self.state in {"Idle", "Stopped"}
        recording = self.state == "Recording"
        playing = self.state == "Playing"
        self.record_button.configure(state="normal" if idle else "disabled")
        self.stop_record_button.configure(state="normal" if recording else "disabled")
        self.play_button.configure(state="normal" if idle and self.macro.events else "disabled")
        self.stop_play_button.configure(state="normal" if playing else "disabled")
        for widget in (self.save_button, self.load_button, self.delete_button,
                       self.repeat_entry, self.speed_entry,
                       self.interval_entry):
            widget.configure(state="normal" if idle else "disabled")
        if idle and not self.saved_macro_var.get():
            self.load_button.configure(state="disabled")
            self.delete_button.configure(state="disabled")
        self.saved_macro_combo.configure(state="readonly" if idle else "disabled")

    def start_recording(self) -> None:
        if self.state not in {"Idle", "Stopped"}:
            return
        try:
            self.recorder.start()
        except Exception as exc:
            messagebox.showerror(self._text("recording_error"), str(exc), parent=self.root)
            return
        self.macro.events = []
        self.count_var.set("0")
        self._set_state("Recording")
        self.root.after_idle(self.root.iconify)

    def stop_recording(self) -> None:
        if self.state != "Recording":
            return
        self.macro.events = self.recorder.stop()
        self.count_var.set(str(len(self.macro.events)))
        self._set_state("Stopped")
        self._restore_window()

    def _restore_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(150, lambda: self.root.attributes("-topmost", False))
        self.root.after_idle(self.root.focus_force)

    def _playback_settings(self) -> tuple[int, float, float]:
        try:
            repeat = int(self.repeat_var.get())
            speed = float(self.speed_var.get().lower().rstrip("x"))
            interval = float(self.interval_var.get())
        except ValueError as exc:
            raise ValueError(self._text("settings_numbers")) from exc
        if not 1 <= repeat <= 9999:
            raise ValueError(self._text("repeat_range"))
        if not 0.1 <= speed <= 10.0:
            raise ValueError(self._text("speed_range"))
        if not 0 <= interval <= 86400:
            raise ValueError(self._text("interval_range"))
        return repeat, speed, interval

    def start_playback(self) -> None:
        if self.state not in {"Idle", "Stopped"}:
            return
        try:
            repeat, speed, interval = self._playback_settings()
            self.player.start(self.macro.events, repeat, speed,
                              lambda cancelled, error: self.messages.put(("playback_finished", (cancelled, error))),
                              repeat_interval=interval)
        except Exception as exc:
            messagebox.showerror(self._text("playback_error"), str(exc), parent=self.root)
            return
        self._set_state("Playing")
        self.root.after_idle(self.root.iconify)

    def stop_playback(self) -> None:
        if self.state == "Playing":
            self.player.stop()

    def save(self) -> None:
        try:
            repeat, _, interval = self._playback_settings()
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
        self.path_var.set(str(self.current_path))
        self._refresh_saved_macros(path.name)
        self._set_state("Idle")

    def load(self) -> None:
        filename = self.saved_macro_var.get()
        if not filename:
            messagebox.showinfo(self._text("load_macro"), self._text("no_macros"), parent=self.root)
            return
        path = self.script_directory / filename
        try:
            macro = load_macro(path)
        except MacroValidationError as exc:
            messagebox.showerror(self._text("invalid_macro"), str(exc), parent=self.root)
            return
        self.macro = macro
        self.current_path = Path(path)
        self.name_var.set(macro.name)
        self.repeat_var.set(str(macro.repeat))
        self.interval_var.set(str(macro.repeat_interval))
        self.path_var.set(str(self.current_path))
        self.count_var.set(str(len(macro.events)))
        self._set_state("Idle")

    def delete_selected(self) -> None:
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
            self.path_var.set(self._text("no_file"))
        self.saved_macro_var.set("")
        self._refresh_saved_macros()
        self._update_controls()

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
            self.recorder.stop()
        self.player.stop()
        self.hotkeys.stop()
        self.root.destroy()


def run() -> None:
    root = tk.Tk()
    MacroRecorderApp(root)
    root.mainloop()
