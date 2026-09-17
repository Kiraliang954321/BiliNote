import importlib.util
import pathlib
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


_STUB_MODULE_NAMES = (
    "app",
    "app.utils",
    "app.utils.frame_similarity",
    "app.utils.logger",
    "app.utils.path_helper",
    "ffmpeg",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
)
_MISSING = object()


def _install_stubs():
    app_mod = types.ModuleType("app")
    utils_pkg = types.ModuleType("app.utils")

    logger_mod = types.ModuleType("app.utils.logger")

    class _Logger:
        @staticmethod
        def info(*_args, **_kwargs):
            return None

        @staticmethod
        def warning(*_args, **_kwargs):
            return None

        @staticmethod
        def error(*_args, **_kwargs):
            return None

    def _get_logger(_name):
        return _Logger()

    logger_mod.get_logger = _get_logger

    path_helper_mod = types.ModuleType("app.utils.path_helper")
    frame_similarity_mod = types.ModuleType("app.utils.frame_similarity")
    frame_similarity_mod.frames_are_similar = lambda *_args: False
    ffmpeg_mod = types.ModuleType("ffmpeg")

    pil_mod = types.ModuleType("PIL")
    pil_image_mod = types.ModuleType("PIL.Image")
    pil_draw_mod = types.ModuleType("PIL.ImageDraw")
    pil_font_mod = types.ModuleType("PIL.ImageFont")

    class _FakeImage:
        pass

    class _FakeImageDraw:
        @staticmethod
        def Draw(*_args, **_kwargs):
            return None

    class _FakeImageFont:
        @staticmethod
        def truetype(*_args, **_kwargs):
            return None

        @staticmethod
        def load_default():
            return None

    pil_image_mod.Image = _FakeImage
    pil_draw_mod.ImageDraw = _FakeImageDraw
    pil_font_mod.ImageFont = _FakeImageFont

    def _get_app_dir(name):
        return name

    path_helper_mod.get_app_dir = _get_app_dir
    ffmpeg_mod.probe = lambda *_args, **_kwargs: {"format": {"duration": "0"}}

    sys.modules.setdefault("app", app_mod)
    sys.modules.setdefault("app.utils", utils_pkg)
    sys.modules["PIL"] = pil_mod
    sys.modules["PIL.Image"] = pil_image_mod
    sys.modules["PIL.ImageDraw"] = pil_draw_mod
    sys.modules["PIL.ImageFont"] = pil_font_mod
    sys.modules["ffmpeg"] = ffmpeg_mod
    sys.modules["app.utils.frame_similarity"] = frame_similarity_mod
    sys.modules["app.utils.logger"] = logger_mod
    sys.modules["app.utils.path_helper"] = path_helper_mod


def _load_video_reader_module():
    previous_modules = {name: sys.modules.get(name, _MISSING) for name in _STUB_MODULE_NAMES}
    _install_stubs()
    try:
        root = pathlib.Path(__file__).resolve().parents[1]
        module_path = root / "app" / "utils" / "video_reader.py"
        spec = importlib.util.spec_from_file_location("video_reader", module_path)
        if spec is None or spec.loader is None:
            raise ImportError("video_reader module spec not found")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous_module in previous_modules.items():
            if previous_module is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous_module


video_reader_module = _load_video_reader_module()
VideoReader = video_reader_module.VideoReader


def _make_fake_ffmpeg_runner(colors_by_second):
    def _runner(cmd, check=True):
        output_path = next((arg for arg in cmd if isinstance(arg, str) and arg.endswith(".jpg")), None)
        if output_path is None:
            raise AssertionError("Output path not found in ffmpeg cmd")
        match = re.search(r"frame_(\d{2})_(\d{2})\.jpg$", output_path)
        if match is None:
            raise AssertionError("Unexpected output path")
        sec = int(match.group(1)) * 60 + int(match.group(2))
        payload = colors_by_second[sec]
        with open(output_path, "wb") as f:
            f.write(payload)
        return 0

    return _runner


class TestVideoReaderDeduplicateFrames(unittest.TestCase):
    def test_extract_frames_skips_adjacent_duplicates_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_dir = pathlib.Path(tmp_dir) / "frames"
            grid_dir = pathlib.Path(tmp_dir) / "grids"
            reader = VideoReader(
                video_path="dummy.mp4",
                frame_interval=1,
                frame_dir=str(frame_dir),
                grid_dir=str(grid_dir),
            )

            fake_colors = {
                0: b"frame-a",
                1: b"frame-a",
                2: b"frame-b",
                3: b"frame-b",
            }

            with patch.object(video_reader_module.ffmpeg, "probe", return_value={"format": {"duration": "4"}}), \
                    patch.object(video_reader_module.subprocess, "run", side_effect=_make_fake_ffmpeg_runner(fake_colors)):
                paths = reader.extract_frames(max_frames=10)

            names = [pathlib.Path(p).name for p in paths]
            self.assertEqual(names, ["frame_00_00.jpg", "frame_00_02.jpg"])

    def test_perceptual_mode_retains_latest_frame_of_adjacent_cluster(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            reader = VideoReader(
                video_path="dummy.mp4",
                frame_interval=1,
                frame_dir=str(pathlib.Path(tmp_dir) / "frames"),
                grid_dir=str(pathlib.Path(tmp_dir) / "grids"),
                dedupe_mode="perceptual_latest",
            )
            fake_colors = {second: f"frame-{second}".encode() for second in range(4)}

            # Only chronological pairs 0~1 and 1~2 are one visual state.
            similar_pairs = {("frame_00_00.jpg", "frame_00_01.jpg"), ("frame_00_01.jpg", "frame_00_02.jpg")}
            def are_similar(previous, current):
                return (pathlib.Path(previous).name, pathlib.Path(current).name) in similar_pairs

            with patch.object(video_reader_module.ffmpeg, "probe", return_value={"format": {"duration": "4"}}), \
                    patch.object(video_reader_module.subprocess, "run", side_effect=_make_fake_ffmpeg_runner(fake_colors)), \
                    patch.object(video_reader_module, "frames_are_similar", side_effect=are_similar):
                paths = reader.extract_frames(max_frames=10)

            self.assertEqual(
                [pathlib.Path(path).name for path in paths],
                ["frame_00_02.jpg", "frame_00_03.jpg"],
            )
            self.assertFalse((pathlib.Path(reader.frame_dir) / "frame_00_00.jpg").exists())
            self.assertFalse((pathlib.Path(reader.frame_dir) / "frame_00_01.jpg").exists())

    def test_perceptual_similarity_failure_retains_frames_and_continues(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            reader = VideoReader(
                video_path="dummy.mp4",
                frame_interval=1,
                frame_dir=str(pathlib.Path(tmp_dir) / "frames"),
                grid_dir=str(pathlib.Path(tmp_dir) / "grids"),
                dedupe_mode="perceptual_latest",
            )
            fake_colors = {second: f"frame-{second}".encode() for second in range(3)}

            with patch.object(video_reader_module.ffmpeg, "probe", return_value={"format": {"duration": "3"}}), \
                    patch.object(video_reader_module.subprocess, "run", side_effect=_make_fake_ffmpeg_runner(fake_colors)), \
                    patch.object(video_reader_module, "frames_are_similar", side_effect=RuntimeError("bad image")):
                paths = reader.extract_frames(max_frames=10)

            self.assertEqual(
                [pathlib.Path(path).name for path in paths],
                ["frame_00_00.jpg", "frame_00_01.jpg", "frame_00_02.jpg"],
            )
            self.assertTrue((pathlib.Path(reader.frame_dir) / "frame_00_00.jpg").exists())
            self.assertTrue((pathlib.Path(reader.frame_dir) / "frame_00_01.jpg").exists())
            self.assertTrue((pathlib.Path(reader.frame_dir) / "frame_00_02.jpg").exists())


if __name__ == "__main__":
    unittest.main()
