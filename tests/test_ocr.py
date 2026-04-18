from __future__ import annotations

from pathlib import Path

import pytest

import xyb.ocr as ocr


def test_resolve_backend_prefers_paddle_then_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "backend_available", lambda name: name in {"paddle", "tesseract"})
    assert ocr.resolve_backend("auto") == "paddle"


def test_resolve_backend_returns_tesseract_when_only_tesseract_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "backend_available", lambda name: name == "tesseract")
    assert ocr.resolve_backend("auto") == "tesseract"


def test_read_image_text_uses_paddle_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"fake")

    monkeypatch.setattr(ocr, "resolve_backend", lambda requested="auto": "paddle")
    monkeypatch.setattr(ocr, "_read_image_text_paddle", lambda path: "中文结果")

    assert ocr.read_image_text(image, backend="auto") == "中文结果"
