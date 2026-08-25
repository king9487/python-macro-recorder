import json
import tempfile
import unittest
from pathlib import Path

from macro_recorder.models import Macro, MacroEvent, MacroValidationError
from macro_recorder.storage import load_macro, save_macro


class ModelStorageTests(unittest.TestCase):
    def test_round_trip(self):
        macro = Macro(name="Test", repeat=3, repeat_interval=1.5, events=[
            MacroEvent(type="keyboard", action="down", key="a", delay=0.25),
            MacroEvent(type="mouse", action="scroll", dx=0, dy=-2, delay=0.1),
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "macro.json"
            save_macro(macro, path)
            loaded = load_macro(path)
        self.assertEqual(loaded, macro)

    def test_missing_optional_fields(self):
        macro = Macro.from_dict({"events": [{"type": "mouse", "action": "scroll", "dy": 1}]})
        self.assertEqual(macro.name, "Untitled Macro")
        self.assertEqual(macro.repeat_interval, 0.0)
        self.assertEqual(macro.events[0].dx, 0)

    def test_invalid_event_is_rejected(self):
        with self.assertRaisesRegex(MacroValidationError, "non-negative"):
            Macro.from_dict({"events": [{"type": "keyboard", "action": "down", "key": "a", "delay": -1}]})

    def test_bad_json_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaisesRegex(MacroValidationError, "line 1"):
                load_macro(path)


if __name__ == "__main__":
    unittest.main()
