import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER_PATH = ROOT / "app" / "utils" / "screenshot_marker.py"
POLICY_PATH = ROOT / "app" / "services" / "screenshot_policy.py"

# Load the pure policy without importing app/__init__.py and its web dependencies.
app_package = types.ModuleType("app")
app_package.__path__ = [str(ROOT / "app")]
utils_package = types.ModuleType("app.utils")
utils_package.__path__ = [str(ROOT / "app" / "utils")]
sys.modules.setdefault("app", app_package)
sys.modules.setdefault("app.utils", utils_package)
marker_spec = importlib.util.spec_from_file_location("app.utils.screenshot_marker", MARKER_PATH)
marker_module = importlib.util.module_from_spec(marker_spec)
sys.modules[marker_spec.name] = marker_module
marker_spec.loader.exec_module(marker_module)
policy_spec = importlib.util.spec_from_file_location("screenshot_policy", POLICY_PATH)
policy_module = importlib.util.module_from_spec(policy_spec)
sys.modules[policy_spec.name] = policy_module
policy_spec.loader.exec_module(policy_module)
apply_screenshot_policy = policy_module.apply_screenshot_policy
extract_screenshot_timestamps = marker_module.extract_screenshot_timestamps


class TestScreenshotPolicy(unittest.TestCase):
    def timestamps(self, markdown):
        return [timestamp for _, timestamp in extract_screenshot_timestamps(markdown)]

    def test_contiguous_run_keeps_last_math_intent(self):
        markdown = "\n".join(f"*Screenshot-[02:{second:02d}]*" for second in (0, 6, 12, 18))
        result = apply_screenshot_policy(markdown, "math_course", 420)
        self.assertEqual(self.timestamps(result), [138])

    def test_directly_adjacent_markers_keep_last_math_intent(self):
        markdown = "Screenshot-[02:00]Screenshot-[02:06]"
        result = apply_screenshot_policy(markdown, "math_course", 420)
        self.assertEqual(self.timestamps(result), [126])

    def test_min_gap_keeps_non_transitive_same_section_intents(self):
        markdown = "## First\nScreenshot-[00:00]\ntext\nScreenshot-[00:30]\ntext\nScreenshot-[01:00]"
        result = apply_screenshot_policy(markdown, "math_course", 420)
        self.assertEqual(self.timestamps(result), [0, 60])

    def test_min_gap_is_limited_to_heading_semantic_unit(self):
        markdown = "## First\nScreenshot-[01:00]\ntext\nScreenshot-[01:30]\n### Second\nScreenshot-[01:45]"
        result = apply_screenshot_policy(markdown, "math_course", 420)
        self.assertEqual(self.timestamps(result), [90, 105])

    def test_dense_same_section_intents_remain_distributed_before_hard_cap(self):
        markers = []
        for timestamp in range(0, 421, 6):
            minutes, seconds = divmod(timestamp, 60)
            markers.append(f"Screenshot-[{minutes:02d}:{seconds:02d}]\ntext")
        result = apply_screenshot_policy("## First\n" + "\n".join(markers), "math_course", 420)
        timestamps = self.timestamps(result)
        self.assertGreater(len(timestamps), 1)
        self.assertLessEqual(len(timestamps), 6)

    def test_hard_cap_for_420_seconds_limits_pathological_input(self):
        markdown = "\n".join(
            f"## Section {index}\nScreenshot-[{index:02d}:00]" for index in range(72)
        )
        result = apply_screenshot_policy(markdown, "math_course", 420)
        self.assertLessEqual(len(self.timestamps(result)), 6)

    def test_representatives_use_even_targets_and_later_tie_break(self):
        markdown = "\n".join(
            [
                "## A\nScreenshot-[00:20]",
                "## B\nScreenshot-[00:40]",
                "## C\nScreenshot-[01:00]",
                "## D\nScreenshot-[01:20]",
            ]
        )
        result = apply_screenshot_policy(markdown, "math_course", 100)
        self.assertEqual(self.timestamps(result), [40, 60])

    def test_fill_uses_maximum_minimum_temporal_distance(self):
        markdown = "## A\nScreenshot-[00:20]\ntext\nScreenshot-[01:20]\ntext\nScreenshot-[02:30]\n## B\nScreenshot-[03:20]"
        result = apply_screenshot_policy(markdown, "math_course", 225)
        self.assertEqual(self.timestamps(result), [20, 150, 200])

    def test_general_mode_does_not_filter_intents(self):
        markdown = "Screenshot-[02:00]\nScreenshot-[02:06]\n*Screenshot-[02:12]*"
        result = apply_screenshot_policy(markdown, "general", 420)
        self.assertEqual(result, markdown)
        self.assertEqual(self.timestamps(result), [120, 126, 132])


if __name__ == "__main__":
    unittest.main()
