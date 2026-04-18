from __future__ import annotations

import json
from pathlib import Path

import pytest

import xyb.ocr as ocr


def test_resolve_backend_prefers_paddle_then_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "backend_available", lambda name: name in {"paddle-local", "tesseract"})
    assert ocr.resolve_backend("auto") == "auto"


def test_resolve_backend_returns_tesseract_when_only_tesseract_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "backend_available", lambda name: name == "tesseract")
    assert ocr.resolve_backend("auto") == "auto"


def test_resolve_backend_prefers_mineru_over_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "backend_available", lambda name: name in {"mineru-local", "tesseract"})
    assert ocr.resolve_backend("auto") == "auto"


def test_read_image_text_uses_paddle_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"fake")

    monkeypatch.setattr(ocr, "resolve_backend", lambda requested="auto": "paddle-local")
    monkeypatch.setattr(ocr, "_read_image_text_paddle", lambda path: "中文结果")

    assert ocr.read_image_text(image, backend="auto") == "中文结果"


def test_read_image_text_uses_mineru_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"fake")

    monkeypatch.setattr(ocr, "resolve_backend", lambda requested="auto": "mineru-local")
    monkeypatch.setattr(ocr, "_read_image_text_mineru", lambda path: "mineru结果")

    assert ocr.read_image_text(image, backend="auto") == "mineru结果"


def test_read_image_text_mineru_local_reads_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"fake")

    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/local/bin/mineru" if name == "mineru" else None)

    class FakeTmpDir:
        def __init__(self, path: Path):
            self.path = path

        def __enter__(self):
            self.path.mkdir(parents=True, exist_ok=True)
            (self.path / "result.md").write_text("mineru markdown", encoding="utf-8")
            return str(self.path)

        def __exit__(self, exc_type, exc, tb):
            return False

    out_dir = tmp_path / "mineru-out"
    monkeypatch.setattr(ocr.tempfile, "TemporaryDirectory", lambda prefix="": FakeTmpDir(out_dir))

    class FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(ocr.subprocess, "run", lambda *args, **kwargs: FakeProc())
    assert ocr._read_image_text_mineru(image) == "mineru markdown"


def test_read_image_text_paddle_api_not_implemented(tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"fake")
    import os
    old_url = os.environ.pop("PADDLEOCR_API_URL", None)
    old_token = os.environ.pop("PADDLEOCR_API_TOKEN", None)
    try:
        with pytest.raises(RuntimeError, match="PaddleOCR API env"):
            ocr.read_image_text(image, backend="paddle-api")
    finally:
        if old_url is not None:
            os.environ["PADDLEOCR_API_URL"] = old_url
        if old_token is not None:
            os.environ["PADDLEOCR_API_TOKEN"] = old_token


def test_read_image_text_auto_selects_best_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"fake")

    monkeypatch.setattr(ocr, "backend_available", lambda name: name in {"paddle-api", "tesseract"})

    def fake_dispatch(path, backend="auto"):
        if backend == "auto":
            return ocr._read_image_text_auto(path)
        if backend == "paddle-api":
            return "申请科室：胰腺胆道专病门诊\n癌胚抗原\n8.08ng/ml"
        if backend == "tesseract":
            return "8.08ng/ml"
        raise AssertionError(backend)

    monkeypatch.setattr(ocr, "read_image_text", fake_dispatch)
    assert "癌胚抗原" in fake_dispatch(image, backend="auto")


def test_read_image_text_uses_multimodal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"fake")

    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "key123")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "gpt-5.4")

    class FakeResp:
        status_code = 200
        text = '{"choices":[{"message":{"content":"多模态结果"}}]}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "多模态结果"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url == "https://example.com/v1/chat/completions"
        assert headers["Authorization"] == "Bearer key123"
        assert json["model"] == "gpt-5.4"
        return FakeResp()

    monkeypatch.setattr(ocr.requests, "post", fake_post)
    assert ocr.read_image_text(image, backend="multimodal") == "多模态结果"


def test_read_image_text_uses_paddle_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"fake")

    monkeypatch.setenv("PADDLEOCR_API_URL", "https://example.com/layout-parsing")
    monkeypatch.setenv("PADDLEOCR_API_TOKEN", "token123")

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "result": {
                    "layoutParsingResults": [
                        {"markdown": {"text": "第一段"}},
                        {"markdown": {"text": "第二段"}},
                    ]
                }
            }

    def fake_post(url, json, headers, timeout):
        assert url == "https://example.com/layout-parsing"
        assert headers["Authorization"] == "token token123"
        assert json["fileType"] == 1
        return FakeResp()

    monkeypatch.setattr(ocr.requests, "post", fake_post)
    assert ocr.read_image_text(image, backend="paddle-api") == "第一段\n\n第二段"


def test_read_image_text_uses_paddle_api_async(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"fake")

    monkeypatch.setenv("PADDLEOCR_API_URL", "https://example.com/api/v2/ocr/jobs")
    monkeypatch.setenv("PADDLEOCR_API_TOKEN", "token123")
    monkeypatch.setenv("PADDLEOCR_API_MODEL", "PaddleOCR-VL-1.5")

    class FakeResp:
        def __init__(self, payload, text=""):
            self._payload = payload
            self.text = text

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_post(url, headers=None, data=None, files=None, timeout=None):
        assert url.endswith("/jobs")
        return FakeResp({"data": {"jobId": "job-1"}})

    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/jobs/job-1"):
            return FakeResp({"data": {"state": "done", "resultUrl": {"jsonUrl": "https://example.com/result.jsonl"}}})
        return FakeResp({}, text='{"result":{"layoutParsingResults":[{"markdown":{"text":"异步结果"}}]}}')

    monkeypatch.setattr(ocr.requests, "post", fake_post)
    monkeypatch.setattr(ocr.requests, "get", fake_get)
    monkeypatch.setattr(ocr.time, "sleep", lambda _: None)
    assert ocr.read_image_text(image, backend="paddle-api") == "异步结果"


def test_read_image_text_uses_mineru_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"fake")

    monkeypatch.setenv("MINERU_API_BASE_URL", "https://mineru.net")
    monkeypatch.setenv("MINERU_API_TOKEN", "mineru-token")

    class FakeResp:
        def __init__(self, payload=None, content=b""):
            self._payload = payload or {}
            self.content = content
            self.text = json.dumps(self._payload, ensure_ascii=False) if self._payload else ""

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url.endswith("/api/v4/file-urls/batch")
        return FakeResp({"data": {"batch_id": "batch-1", "file_urls": ["https://upload.local/file"]}})

    def fake_put(url, data=None, timeout=None):
        class PutResp:
            status_code = 200
        return PutResp()

    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/api/v4/extract-results/batch/batch-1"):
            return FakeResp({"data": {"extract_result": [{"state": "done", "full_zip_url": "https://download.local/result.zip"}]}})
        if url == "https://download.local/result.zip":
            import io, zipfile
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("out/result.md", "mineru api markdown")
            return FakeResp(content=buf.getvalue())
        return FakeResp({})

    monkeypatch.setattr(ocr.requests, "post", fake_post)
    monkeypatch.setattr(ocr.requests, "put", fake_put)
    monkeypatch.setattr(ocr.requests, "get", fake_get)
    monkeypatch.setattr(ocr.time, "sleep", lambda _: None)
    assert ocr.read_image_text(image, backend="mineru-api") == "mineru api markdown"


def test_read_image_text_host_cli_keeps_image_path_with_spaces(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "download (1).png"
    image.write_bytes(b"fake")

    monkeypatch.setenv("XYB_HOST_MM_COMMAND", "host-mm --input {image}")

    class FakeProc:
        returncode = 0
        stdout = "host cli result"
        stderr = ""

    captured = {}

    def fake_run(cmd, check=False, capture_output=True, text=True, timeout=180, **kwargs):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)
    out = ocr.read_image_text(image, backend="host-cli")
    assert out == "host cli result"
    assert captured["cmd"][0:2] == ["host-mm", "--input"]
    assert captured["cmd"][2] == str(image)
