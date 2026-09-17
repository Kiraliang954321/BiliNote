import importlib.util
import pathlib
import sys
import types
import unittest
from enum import Enum

from pydantic import ValidationError


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _install_router_stubs():
    class Router:
        def post(self, *_args, **_kwargs):
            return lambda func: func

        get = post

    fastapi = types.ModuleType("fastapi")
    fastapi.APIRouter = Router
    fastapi.HTTPException = Exception
    fastapi.BackgroundTasks = object
    fastapi.UploadFile = object
    fastapi.File = lambda *_args, **_kwargs: None
    fastapi.Request = object
    sys.modules["fastapi"] = fastapi
    responses = types.ModuleType("fastapi.responses")
    responses.StreamingResponse = object
    sys.modules["fastapi.responses"] = responses
    sys.modules["httpx"] = types.ModuleType("httpx")

    for package in ("app", "app.db", "app.enmus", "app.exceptions", "app.services", "app.utils", "app.validators", "app.models", "app.routers"):
        sys.modules[package] = types.ModuleType(package)

    modules = {
        "app.models.transcriber_model": {"TranscriptSegment": object},
        "app.db.video_task_dao": {"get_task_by_video": lambda *_args: None},
        "app.enmus.exception": {"NoteErrorEnum": types.SimpleNamespace(PLATFORM_NOT_SUPPORTED=types.SimpleNamespace(code=1, message="unsupported"))},
        "app.enmus.note_enums": {"DownloadQuality": Enum("DownloadQuality", "fast medium slow")},
        "app.exceptions.note": {"NoteError": ValueError},
        "app.services.note": {"NoteGenerator": object, "logger": types.SimpleNamespace()},
        "app.services.task_serial_executor": {"task_serial_executor": object()},
        "app.utils.response": {"ResponseWrapper": types.SimpleNamespace(success=lambda *_args, **_kwargs: None, error=lambda *_args, **_kwargs: None)},
        "app.utils.url_parser": {"extract_video_id": lambda *_args: "id", "normalize_video_url": lambda url: url},
        "app.validators.video_url_validator": {"is_supported_video_url": lambda _url: True},
        "app.enmus.task_status_enums": {"TaskStatus": types.SimpleNamespace(PENDING="PENDING", SUCCESS="SUCCESS", FAILED="FAILED")},
    }
    for name, attrs in modules.items():
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        sys.modules[name] = module


ROOT = pathlib.Path(__file__).resolve().parents[1]
_install_router_stubs()
GPTSource = _load_module("app.models.gpt_model", ROOT / "app" / "models" / "gpt_model.py").GPTSource
VideoRequest = _load_module("app.routers.note", ROOT / "app" / "routers" / "note.py").VideoRequest
QUALITY_FAST = sys.modules["app.enmus.note_enums"].DownloadQuality.fast


class TestContentProfileContract(unittest.TestCase):
    def _request(self, **overrides):
        data = {"video_url": "https://example.test/video", "platform": "bilibili", "quality": QUALITY_FAST, "model_name": "test-model", "provider_id": "test-provider"}
        data.update(overrides)
        return VideoRequest(**data)

    def test_request_defaults_to_general(self):
        self.assertEqual(self._request().content_profile, "general")

    def test_request_accepts_math_course(self):
        self.assertEqual(self._request(content_profile="math_course").content_profile, "math_course")

    def test_request_rejects_unsupported_profile(self):
        with self.assertRaises(ValidationError):
            self._request(content_profile="unsupported")

    def test_gpt_source_defaults_to_general(self):
        self.assertEqual(GPTSource(segment=[], title="title", tags="tags").content_profile, "general")


if __name__ == "__main__":
    unittest.main()
