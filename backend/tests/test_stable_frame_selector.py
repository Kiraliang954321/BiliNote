import importlib.util
import pathlib
import sys
import unittest

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "services" / "stable_frame_selector.py"
spec = importlib.util.spec_from_file_location("stable_frame_selector", MODULE_PATH)
selector_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = selector_module
spec.loader.exec_module(selector_module)
StableFrameSelector = selector_module.StableFrameSelector


class TestStableFrameSelector(unittest.TestCase):
    @staticmethod
    def frame(value):
        return np.full((180, 320), value, dtype=np.uint8)

    def test_selects_settled_frame_after_writing_stops(self):
        # The intent is during a sequence of changes; writing stops at 14s.
        values = {8: 0, 9: 20, 10: 40, 11: 60, 12: 80, 13: 100, 14: 100, 15: 100, 16: 100, 17: 100, 18: 100}
        selected = StableFrameSelector(lambda timestamp: self.frame(values[timestamp]), 18).select(10)
        self.assertGreaterEqual(selected, 14)

    def test_forward_scene_cut_does_not_select_stable_next_scene(self):
        values = {8: 30, 9: 30, 10: 30, 11: 230, 12: 230, 13: 230, 14: 230, 15: 230, 16: 230, 17: 230, 18: 230}
        selected = StableFrameSelector(lambda timestamp: self.frame(values[timestamp]), 18).select(10)
        self.assertLess(selected, 11)

    def test_pre_intent_cut_does_not_discard_intent_scene(self):
        values = {8: 10, 9: 220, 10: 220, 11: 220, 12: 220, 13: 220, 14: 220, 15: 220, 16: 220, 17: 220, 18: 220}
        selected = StableFrameSelector(lambda timestamp: self.frame(values[timestamp]), 18).select(10)
        self.assertGreaterEqual(selected, 10)

    def test_loader_failure_returns_original_intent(self):
        selected = StableFrameSelector(lambda timestamp: (_ for _ in ()).throw(RuntimeError("no frame")), 18).select(10)
        self.assertEqual(selected, 10)

    def test_insufficient_neighborhood_returns_original_intent(self):
        selected = StableFrameSelector(lambda timestamp: self.frame(10), 1).select(0)
        self.assertEqual(selected, 0)


if __name__ == "__main__":
    unittest.main()
