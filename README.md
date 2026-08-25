# Python Macro Recorder

A small Windows desktop application that records keyboard and mouse input to readable JSON and replays it with configurable repetition and speed.

The interface includes a Language dropdown and can switch immediately between English and Traditional Chinese (繁體中文).

## Requirements and installation

- Windows 10 or 11
- Python 3.10 or newer

From PowerShell in this directory:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

Use the buttons or global hotkeys:

- **F8** starts a new recording and replaces the events currently in memory.
- **F9** stops recording.
- **F10** immediately requests playback cancellation.

F8, F9, and F10 are never included in recordings. Save uses the Macro name and writes the current macro to `script/<name>.json`. The Saved macros dropdown lists these files; selecting one loads and validates it. Delete Selected removes the chosen file after confirmation. Repeat count accepts 1–9999. Repeat interval controls the wait in seconds between complete repetitions. Playback speed accepts 0.1–10.0, with `2.0` twice as fast and `0.5` half speed.

When recording or playback starts, the application minimizes automatically. Pressing F9 stops recording and restores the application to the foreground. Playback completion, playback errors, and F10 cancellation also restore it to the foreground.

## JSON format

Files contain a version, display name, saved repeat count, and an ordered event list. Every event has a delay in seconds since the preceding recorded event. Missing `version`, `name`, `repeat`, `delay`, and scroll axes receive safe defaults.

```json
{
  "version": 1,
  "name": "Example",
  "repeat": 2,
  "repeat_interval": 1.5,
  "events": [
    {"type": "mouse", "action": "move", "x": 800, "y": 450, "delay": 0.12},
    {"type": "keyboard", "action": "down", "key": "a", "delay": 0.05},
    {"type": "keyboard", "action": "up", "key": "a", "delay": 0.03}
  ]
}
```

Keyboard keys are stored as characters, pynput special-key names such as `enter` or `ctrl_l`, or `vk:<number>` when only a Windows virtual-key code is available. Mouse actions are `move`, `down`, `up`, and `scroll`.

## Design

- `models.py` defines and validates the JSON-facing data model.
- `storage.py` handles UTF-8 JSON loading and saving.
- `recorder.py` owns pynput listeners and timestamps accepted events.
- `player.py` runs playback on a daemon thread and uses interruptible waits.
- `hotkeys.py` owns the independent global emergency-key listener.
- `gui.py` owns tkinter state. Worker callbacks communicate through a queue polled by tkinter.

Run automated tests with:

```powershell
python -m unittest discover -s tests -v
```

## Known limitations and risks

- Global input control can trigger destructive actions in whichever window has focus. Test new macros in a safe application first.
- Playback uses absolute screen coordinates, so changed monitor layout, resolution, scaling, or window placement can change results.
- Some elevated applications, secure desktops, antivirus tools, games, and remote-desktop environments may reject synthetic input or global hooks. Running with matching privileges may be required.
- Keyboard layout differences can affect character replay. Password fields and other sensitive input are recorded as plain JSON key events; protect saved files accordingly.
- Mouse movement is intentionally throttled (20 ms or 5 pixels) to keep files manageable, so freehand motion is approximate.
- Playback does not restore keys or mouse buttons if cancellation happens between a down and up event. Release any stuck modifier manually.
