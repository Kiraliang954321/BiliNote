import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.modules.setdefault("app", types.ModuleType("app"))
sys.modules.setdefault("app.gpt", types.ModuleType("app.gpt"))


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load_module("app.gpt.prompt", ROOT / "app" / "gpt" / "prompt.py")
generate_base_prompt = _load_module(
    "app.gpt.prompt_builder", ROOT / "app" / "gpt" / "prompt_builder.py"
).generate_base_prompt


class TestMathCoursePrompt(unittest.TestCase):
    def test_math_course_uses_latex_first_sparse_screenshot_rules(self):
        prompt = generate_base_prompt(
            "Calculus", "00:00 - derivative", "math", _format=["screenshot"],
            content_profile="math_course",
        )

        self.assertIn("LaTeX/Markdown", prompt)
        self.assertIn("完整题目图片", prompt)
        self.assertIn("几何图形、函数/坐标图", prompt)
        self.assertIn("完整板书", prompt)
        self.assertIn("完整页推导", prompt)
        self.assertIn("不要逐一枚举", prompt)
        self.assertIn("不要连续输出 Screenshot", prompt)
        self.assertIn("每个知识点一张代表性截图", prompt)
        self.assertIn("书写完成后", prompt)
        self.assertIn("45 秒", prompt)
        self.assertIn("*Screenshot-[mm:ss]", prompt)

    def test_math_course_requires_renderable_latex_delimiters_not_code_spans(self):
        for screenshot_format in ([], ["screenshot"]):
            prompt = generate_base_prompt(
                "Calculus", "00:00 - derivative", "math", _format=screenshot_format,
                content_profile="math_course",
            )

            self.assertIn("行内公式使用 `$...$`", prompt)
            self.assertIn("展示公式和推导使用 `$$...$$`", prompt)
            self.assertIn("不要将 LaTeX 公式或命令放在 Markdown 反引号或代码跨度中", prompt)

    def test_math_course_without_screenshot_keeps_latex_rule_only(self):
        prompt = generate_base_prompt(
            "Calculus", "00:00 - derivative", "math", _format=[],
            content_profile="math_course",
        )

        self.assertIn("LaTeX/Markdown", prompt)
        self.assertNotIn("*Screenshot-[mm:ss]", prompt)
        self.assertNotIn("完整题目图片", prompt)
        self.assertNotIn("每个知识点一张代表性截图", prompt)
        self.assertNotIn("45 秒", prompt)

    def test_general_does_not_include_math_course_rules(self):
        prompt = generate_base_prompt(
            "General", "00:00 - content", "general", _format=["screenshot"],
            content_profile="general",
        )

        self.assertNotIn("LaTeX/Markdown", prompt)
        self.assertNotIn("每个知识点一张代表性截图", prompt)
        self.assertNotIn("45 秒", prompt)


if __name__ == "__main__":
    unittest.main()
