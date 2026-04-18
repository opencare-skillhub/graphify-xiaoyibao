from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

OCR_BACKENDS = ("auto", "paddle", "mineru", "tesseract")


def backend_available(name: str) -> bool:
    name = (name or "").lower().strip()
    if name == "tesseract":
        return shutil.which("tesseract") is not None
    if name == "paddle":
        return importlib.util.find_spec("paddleocr") is not None
    if name == "mineru":
        return shutil.which("mineru") is not None or importlib.util.find_spec("mineru") is not None
    return False


def resolve_backend(requested: str = "auto") -> str:
    req = (requested or "auto").lower().strip()
    if req != "auto":
        if not backend_available(req):
            raise RuntimeError(f"OCR backend '{req}' is not available in the current environment")
        if req in {"paddle", "mineru"}:
            raise RuntimeError(f"OCR backend '{req}' is planned but not implemented yet in xyb")
        return req

    for candidate in ("paddle", "mineru", "tesseract"):
        if not backend_available(candidate):
            continue
        if candidate in {"paddle", "mineru"}:
            continue
        return candidate
    return "none"


def read_image_text(path: Path, *, backend: str = "auto") -> str:
    selected = resolve_backend(backend)
    if selected == "tesseract":
        return _read_image_text_tesseract(path)
    if selected == "none":
        return ""
    raise RuntimeError(f"OCR backend '{selected}' is not implemented yet in xyb")


def _read_image_text_tesseract(path: Path) -> str:
    src = path
    tmp_png: Path | None = None
    try:
        if path.suffix.lower() in {".heic", ".heif"} and shutil.which("sips"):
            fd, name = tempfile.mkstemp(suffix=".png")
            try:
                subprocess.run(["sips", "-s", "format", "png", str(path), "--out", name], check=False, capture_output=True)
            finally:
                os.close(fd)
            maybe = Path(name)
            if maybe.exists():
                src = maybe
                tmp_png = maybe
        return _run_best_effort_tesseract(src)
    except Exception:
        return ""
    finally:
        if tmp_png is not None and tmp_png.exists():
            tmp_png.unlink(missing_ok=True)


@lru_cache(maxsize=1)
def _tesseract_langs() -> set[str]:
    if shutil.which("tesseract") is None:
        return set()
    try:
        proc = subprocess.run(
            ["tesseract", "--list-langs"],
            check=False,
            capture_output=True,
            text=True,
        )
        lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
        return set(lines[1:]) if len(lines) > 1 else set()
    except Exception:
        return set()


def _preferred_tesseract_lang() -> str | None:
    langs = _tesseract_langs()
    if {"chi_sim", "eng"}.issubset(langs):
        return "chi_sim+eng"
    if {"chi_tra", "eng"}.issubset(langs):
        return "chi_tra+eng"
    if "chi_sim" in langs:
        return "chi_sim"
    if "chi_tra" in langs:
        return "chi_tra"
    if "eng" in langs:
        return "eng"
    return None


def _ocr_score(text: str) -> tuple[int, int, int]:
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    marker_hits = len(re.findall(r"CA\s*\d+|CEA|AFP|CT|病灶|放射学诊断|胰头|腹膜", text, re.I))
    meaningful = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text))
    return (chinese, marker_hits, meaningful)


def _run_best_effort_tesseract(src: Path) -> str:
    lang = _preferred_tesseract_lang()
    variants: list[list[str]] = []
    base = ["tesseract", str(src), "stdout"]
    if lang:
        variants.append(base + ["-l", lang, "--psm", "6"])
        variants.append(base + ["-l", lang, "--psm", "11"])
    variants.append(base + ["--psm", "6"])
    variants.append(base + ["--psm", "11"])

    best = ""
    best_score = (-1, -1, -1)
    for cmd in variants:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        text = (proc.stdout or "").strip()
        score = _ocr_score(text)
        if score > best_score:
            best_score = score
            best = text
    return best
