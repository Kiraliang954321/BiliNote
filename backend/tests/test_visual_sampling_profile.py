import ast
import pathlib
import unittest


NOTE_PATH = pathlib.Path(__file__).resolve().parents[1] / "app" / "services" / "note.py"


class TestVisualSamplingProfileIntegration(unittest.TestCase):
    def test_download_media_selects_perceptual_mode_only_for_math_course(self):
        tree = ast.parse(NOTE_PATH.read_text(encoding="utf-8"))
        download_media = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_download_media"
        )
        reader_call = next(
            node for node in ast.walk(download_media)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "VideoReader"
        )
        dedupe_mode = next(keyword.value for keyword in reader_call.keywords if keyword.arg == "dedupe_mode")

        self.assertIsInstance(dedupe_mode, ast.IfExp)
        self.assertEqual(ast.unparse(dedupe_mode.test), "content_profile == 'math_course'")
        self.assertEqual(ast.unparse(dedupe_mode.body), "PERCEPTUAL_LATEST_DEDUPE")
        self.assertEqual(ast.unparse(dedupe_mode.orelse), "EXACT_MD5_DEDUPE")


if __name__ == "__main__":
    unittest.main()
