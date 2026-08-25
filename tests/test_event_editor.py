import unittest

from macro_recorder.event_editor import EventEditError, EventEditorModel
from macro_recorder.models import MacroEvent


class EventEditorTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            MacroEvent(type="keyboard", action="down", key="w", delay=0.1),
            MacroEvent(type="mouse", action="move", x=10, y=20, delay=0.2),
            MacroEvent(type="mouse", action="scroll", dx=0, dy=-1, delay=0.3),
        ]
        self.editor = EventEditorModel(self.events)

    def test_edit_keyboard_event(self):
        edited = self.editor.edit(0, {"action": "up", "key": "space", "delay": "1.250"})
        self.assertEqual(edited, MacroEvent(type="keyboard", action="up", key="space", delay=1.25))
        self.assertTrue(self.editor.dirty)

    def test_edit_mouse_event(self):
        edited = self.editor.edit(1, {"x": "820", "y": "460", "delay": "0.050"})
        self.assertEqual(edited, MacroEvent(type="mouse", action="move", x=820, y=460, delay=0.05))

    def test_edit_mouse_button_event(self):
        events = [MacroEvent(type="mouse", action="down", button="left", x=10, y=20)]
        editor = EventEditorModel(events)
        edited = editor.edit(0, {"action": "up", "button": "right", "x": "30", "y": "40",
                                 "delay": "0.125"})
        self.assertEqual(edited, MacroEvent(type="mouse", action="up", button="right",
                                            x=30, y=40, delay=0.125))

    def test_edit_mouse_scroll_event(self):
        edited = self.editor.edit(2, {"dx": "2", "dy": "-4", "delay": "0.75"})
        self.assertEqual(edited, MacroEvent(type="mouse", action="scroll", dx=2, dy=-4, delay=0.75))

    def test_delay_validation(self):
        for value in ("-1", "not-a-number", "nan", "inf"):
            with self.subTest(value=value), self.assertRaises(EventEditError):
                self.editor.edit(0, {"action": "down", "key": "w", "delay": value})

    def test_invalid_edit_does_not_mutate_event(self):
        original = self.events[1]
        with self.assertRaises(EventEditError):
            self.editor.edit(1, {"x": "10.5", "y": "20", "delay": "0.2"})
        self.assertIs(self.events[1], original)
        self.assertFalse(self.editor.dirty)

    def test_unrepresentable_keyboard_key_is_rejected_without_mutation(self):
        original = self.events[0]
        with self.assertRaises(EventEditError):
            self.editor.edit(0, {"action": "down", "key": "not_a_real_key", "delay": "0.1"})
        self.assertIs(self.events[0], original)
        self.assertFalse(self.editor.dirty)

    def test_delete_event(self):
        selected = self.editor.delete(1)
        self.assertEqual(selected, 1)
        self.assertEqual([event.action for event in self.events], ["down", "scroll"])
        self.assertTrue(self.editor.dirty)

    def test_move_event_up(self):
        selected = self.editor.move_up(2)
        self.assertEqual(selected, 1)
        self.assertEqual([event.action for event in self.events], ["down", "scroll", "move"])
        self.assertTrue(self.editor.dirty)

    def test_move_event_down(self):
        selected = self.editor.move_down(0)
        self.assertEqual(selected, 1)
        self.assertEqual([event.action for event in self.events], ["move", "down", "scroll"])
        self.assertTrue(self.editor.dirty)

    def test_reordering_preserves_all_event_objects(self):
        original_ids = {id(event) for event in self.events}
        self.editor.move_down(0)
        self.editor.move_up(2)
        self.assertEqual({id(event) for event in self.events}, original_ids)
        self.assertEqual(len(self.events), 3)

    def test_boundary_moves_do_nothing_safely(self):
        original = list(self.events)
        self.assertEqual(self.editor.move_up(0), 0)
        self.assertEqual(self.editor.move_down(2), 2)
        self.assertEqual(self.events, original)
        self.assertFalse(self.editor.dirty)

    def test_dirty_state_resets_after_save_and_load(self):
        self.editor.edit(0, {"action": "up", "key": "w", "delay": "0.1"})
        self.editor.mark_saved()
        self.assertFalse(self.editor.dirty)
        replacement = [MacroEvent(type="keyboard", action="down", key="a")]
        self.editor.load(replacement)
        self.assertIs(self.editor.events, replacement)
        self.assertFalse(self.editor.dirty)

    def test_playback_source_is_same_edited_list(self):
        self.editor.edit(0, {"action": "up", "key": "a", "delay": "0.4"})
        self.assertIs(self.editor.events, self.events)
        self.assertEqual(self.events[0].key, "a")


if __name__ == "__main__":
    unittest.main()
