from __future__ import annotations

import importlib.util
import os
import re
import shutil
import shlex
import subprocess
import tempfile
import json
import time
import zipfile
from functools import lru_cache
from pathlib import Path
import base64

import requests

OCR_BACKENDS = (
    "auto",
    "host-cli",
    "multimodal",
    "paddle-local",
    "paddle-api",
    "mineru-local",
    "mineru-api",
    "tesseract",
)

AUTO_BACKEND_ORDER = (
    "mineru-api",
    "paddle-api",
    "host-cli",
    "multimodal",
    "tesseract",
)

AUTO_EARLY_ACCEPT = {
    "host-cli",
    "paddle-api",
    "mineru-api",
}

_MINERU_FAIL_COUNT = 0
_MINERU_DISABLED = False
_PADDLE_FAIL_COUNT = 0
_PADDLE_DISABLED = False


def _mineru_failure_limit() -> int:
    try:
        return max(1, int(os.getenv("XYB_MINERU_FAIL_LIMIT", "2")))
    except Exception:
        return 2


def _mark_mineru_failure(exc: Exception | None = None) -> None:
    global _MINERU_FAIL_COUNT, _MINERU_DISABLED
    _MINERU_FAIL_COUNT += 1
    if _MINERU_FAIL_COUNT >= _mineru_failure_limit():
        _MINERU_DISABLED = True
    if exc is not None:
        _debug_log("mineru-api degraded", f"fails={_MINERU_FAIL_COUNT}", "disabled=", _MINERU_DISABLED, repr(exc))


def _mark_mineru_success() -> None:
    global _MINERU_FAIL_COUNT, _MINERU_DISABLED
    _MINERU_FAIL_COUNT = 0
    _MINERU_DISABLED = False


def _paddle_failure_limit() -> int:
    try:
        return max(1, int(os.getenv("XYB_PADDLE_FAIL_LIMIT", "2")))
    except Exception:
        return 2


def _mark_paddle_failure(exc: Exception | None = None) -> None:
    global _PADDLE_FAIL_COUNT, _PADDLE_DISABLED
    _PADDLE_FAIL_COUNT += 1
    if _PADDLE_FAIL_COUNT >= _paddle_failure_limit():
        _PADDLE_DISABLED = True
    if exc is not None:
        _debug_log("paddle-api degraded", f"fails={_PADDLE_FAIL_COUNT}", "disabled=", _PADDLE_DISABLED, repr(exc))


def _mark_paddle_success() -> None:
    global _PADDLE_FAIL_COUNT, _PADDLE_DISABLED
    _PADDLE_FAIL_COUNT = 0
    _PADDLE_DISABLED = False


def _debug_enabled() -> bool:
    return os.getenv("XYB_OCR_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _debug_log(*parts) -> None:
    if not _debug_enabled():
        return
    try:
        print("[xyb-ocr-debug]", *parts)
    except Exception:
        pass


def _resp_status(resp) -> object:
    return getattr(resp, "status_code", "NA")


def _resp_text(resp, limit: int = 2000) -> str:
    try:
        text = getattr(resp, "text", "")
        if text:
            return str(text)[:limit]
        if hasattr(resp, "json"):
            return repr(resp.json())[:limit]
    except Exception as exc:
        _debug_log("paddle-api sync exception=", repr(exc))
        return ""
    return ""


def _load_local_env() -> None:
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if not candidate.exists():
            continue
        try:
            for raw in candidate.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
        except Exception:
            continue


_load_local_env()


def backend_available(name: str) -> bool:
    name = (name or "").lower().strip()
    if name == "tesseract":
        return shutil.which("tesseract") is not None
    if name == "host-cli":
        return bool(os.getenv("XYB_HOST_MM_COMMAND"))
    if name == "multimodal":
        return bool(os.getenv("OPENAI_COMPAT_BASE_URL")) and bool(os.getenv("OPENAI_COMPAT_API_KEY")) and bool(os.getenv("OPENAI_COMPAT_MODEL"))
    if name == "paddle-local":
        return (
            importlib.util.find_spec("paddleocr") is not None
            and importlib.util.find_spec("paddle") is not None
        )
    if name == "paddle-api":
        if _PADDLE_DISABLED:
            return False
        return bool(os.getenv("PADDLEOCR_API_TOKEN")) and bool(os.getenv("PADDLEOCR_API_URL"))
    if name == "mineru-local":
        return shutil.which("mineru") is not None or importlib.util.find_spec("mineru") is not None
    if name == "mineru-api":
        if _MINERU_DISABLED:
            return False
        return True
    return False


def resolve_backend(requested: str = "auto") -> str:
    req = (requested or "auto").lower().strip()
    if req != "auto":
        if req in {"host-cli", "multimodal", "paddle-api", "mineru-api"}:
            return req
        if not backend_available(req):
            raise RuntimeError(f"OCR backend '{req}' is not available in the current environment")
        return req

    if any(backend_available(candidate) for candidate in AUTO_BACKEND_ORDER):
        return "auto"
    return "none"


def read_image_text(path: Path, *, backend: str = "auto") -> str:
    selected = resolve_backend(backend)
    if selected == "auto":
        return _read_image_text_auto(path)
    if selected == "host-cli":
        return _read_image_text_host_cli(path)
    if selected == "multimodal":
        return _read_image_text_multimodal(path)
    if selected == "paddle-local":
        return _read_image_text_paddle(path)
    if selected == "paddle-api":
        return _read_image_text_paddle_api(path)
    if selected == "mineru-local":
        return _read_image_text_mineru(path)
    if selected == "mineru-api":
        return _read_image_text_mineru_api(path)
    if selected == "tesseract":
        return _read_image_text_tesseract(path)
    if selected == "none":
        return ""
    raise RuntimeError(f"OCR backend '{selected}' is not implemented yet in xyb")


def _read_image_text_auto(path: Path) -> str:
    best = ""
    best_backend = ""
    best_score = (-1, -1, -1)
    for candidate in AUTO_BACKEND_ORDER:
        if candidate == "mineru-api" and _MINERU_DISABLED:
            _debug_log("auto skip mineru-api (degraded)")
            continue
        if candidate == "paddle-api" and _PADDLE_DISABLED:
            _debug_log("auto skip paddle-api (degraded)")
            continue
        if not backend_available(candidate):
            continue
        try:
            text = read_image_text(path, backend=candidate)
        except Exception as exc:
            _debug_log("auto backend error", candidate, repr(exc))
            continue
        text = (text or "").strip()
        if not text:
            _debug_log("auto backend empty", candidate)
            continue
        if candidate == "mineru-api":
            # 你当前策略：优先 mineru；有结果即收敛，避免继续尝试慢链路
            score = _ocr_score(text)
            _debug_log("auto backend early-accept", candidate, score)
            return text
        score = _ocr_score(text)
        _debug_log("auto backend score", candidate, score, "chars=", len(text))
        if score > best_score:
            best_score = score
            best = text
            best_backend = candidate
        if candidate in AUTO_EARLY_ACCEPT:
            if candidate == "host-cli":
                # 宿主多模态成功时优先直接采用，避免继续尝试后续慢后端
                if score[0] >= 20 or score[2] >= 80:
                    _debug_log("auto backend early-accept", candidate, score)
                    return text
            elif score[0] >= 20 and score[1] >= 1:
                _debug_log("auto backend early-accept", candidate, score)
                return text
    if best_backend:
        _debug_log("auto backend selected", best_backend, best_score)
    return best


def _read_image_text_multimodal(path: Path) -> str:
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    api_key = os.getenv("OPENAI_COMPAT_API_KEY", "")
    model = os.getenv("OPENAI_COMPAT_MODEL", "")
    timeout = int(os.getenv("OPENAI_COMPAT_TIMEOUT", "120"))
    if not base_url or not api_key or not model:
        raise RuntimeError("Multimodal env is missing: OPENAI_COMPAT_BASE_URL / OPENAI_COMPAT_API_KEY / OPENAI_COMPAT_MODEL")

    mime = _guess_image_mime(path)
    try:
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    except Exception:
        return ""

    prompt = (
        "请读取这张医疗图片，尽量完整提取可见文本，并保持结构顺序。"
        "如果是检验单/肿瘤标志物，请区分项目名、结果值、参考值；"
        "如果是CT/放射学报告，请保留检查所见与诊断结论。"
        "只输出纯文本，不要解释。"
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64}"
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=timeout)
        _debug_log("multimodal status=", _resp_status(resp), "url=", f"{base_url}/chat/completions")
        _debug_log("multimodal body=", _resp_text(resp))
        resp.raise_for_status()
        body = resp.json()
        return str(body["choices"][0]["message"]["content"]).strip()
    except Exception:
        return ""


def _read_image_text_host_cli(path: Path) -> str:
    """
    调用宿主 CLI 多模态能力（外部命令注入），命令通过环境变量配置：
    XYB_HOST_MM_COMMAND='my-cli vision --input {image}'
    约定：命令把提取文本写到 stdout。
    """
    template = os.getenv("XYB_HOST_MM_COMMAND", "").strip()
    if not template:
        return ""
    parts = shlex.split(template)
    if not parts:
        return ""
    used_image_token = False
    cmd_parts: list[str] = []
    image_s = str(path)
    for part in parts:
        if "{image}" in part:
            used_image_token = True
            cmd_parts.append(part.replace("{image}", image_s))
        else:
            cmd_parts.append(part)
    if not used_image_token:
        cmd_parts.append(image_s)
    try:
        proc = subprocess.run(
            cmd_parts,
            check=False,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=int(os.getenv("XYB_HOST_MM_TIMEOUT", "180")),
        )
        _debug_log("host-cli status=", proc.returncode, "cmd=", cmd_parts)
        if proc.returncode != 0:
            _debug_log("host-cli stderr=", (proc.stderr or "")[:2000])
            return ""
        return (proc.stdout or "").strip()
    except Exception as exc:
        _debug_log("host-cli exception=", repr(exc))
        return ""


def _guess_image_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _read_image_text_paddle(path: Path) -> str:
    try:
        ocr = _get_paddle_ocr()
        result = ocr.predict(str(path))
    except Exception:
        return ""

    lines: list[str] = []
    for item in result or []:
        if not item:
            continue
        texts = None
        if hasattr(item, "get"):
            texts = item.get("rec_texts")
        elif isinstance(item, dict):
            texts = item.get("rec_texts")
        if not texts:
            continue
        for text in texts:
            text = str(text).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _get_paddle_ocr():
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PaddleOCR is not installed or failed to import") from exc

    return PaddleOCR(
        lang="ch",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def _read_image_text_mineru(path: Path) -> str:
    if shutil.which("mineru") is None:
        raise RuntimeError("MinerU CLI is not available in the current environment")

    with tempfile.TemporaryDirectory(prefix="xyb-mineru-") as tmpdir:
        cmd = ["mineru", "-p", str(path), "-o", tmpdir]
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            return ""

        md_files = sorted(Path(tmpdir).rglob("*.md"))
        if md_files:
            texts: list[str] = []
            for md in md_files:
                try:
                    content = md.read_text(encoding="utf-8", errors="ignore").strip()
                except Exception:
                    content = ""
                if content:
                    texts.append(content)
            if texts:
                return "\n\n".join(texts)

        json_files = sorted(Path(tmpdir).rglob("*.json"))
        for jf in json_files:
            try:
                content = jf.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                content = ""
            if content:
                return content

    return ""


def _read_image_text_paddle_api(path: Path) -> str:
    api_url = os.getenv("PADDLEOCR_API_URL")
    token = os.getenv("PADDLEOCR_API_TOKEN")
    model = os.getenv("PADDLEOCR_API_MODEL", "PaddleOCR-VL-1.5")
    if not api_url or not token:
        raise RuntimeError("PaddleOCR API env is missing: PADDLEOCR_API_URL / PADDLEOCR_API_TOKEN")

    if api_url.rstrip("/").endswith("/jobs"):
        return _read_image_text_paddle_api_async(path, api_url=api_url, token=token, model=model)

    try:
        file_bytes = path.read_bytes()
    except Exception:
        return ""

    file_data = base64.b64encode(file_bytes).decode("ascii")
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "file": file_data,
        "fileType": _paddle_api_file_type(path),
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useChartRecognition": False,
    }
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=120)
        _debug_log("paddle-api sync status=", _resp_status(response), "url=", api_url)
        response.raise_for_status()
        body = response.json()
        _debug_log("paddle-api sync body keys=", list(body.keys())[:20], "body=", repr(body)[:2000])
    except Exception as exc:
        _mark_paddle_failure(exc)
        return ""

    lines: list[str] = []
    for item in body.get("result", {}).get("layoutParsingResults", []) or []:
        markdown = item.get("markdown", {}) if isinstance(item, dict) else {}
        text = str(markdown.get("text", "")).strip()
        if text:
            lines.append(text)
    out = "\n\n".join(lines)
    if out.strip():
        _mark_paddle_success()
    return out


def _read_image_text_paddle_api_async(path: Path, *, api_url: str, token: str, model: str) -> str:
    headers = {
        "Authorization": f"bearer {token}",
    }
    data = {
        "model": model,
        "optionalPayload": json.dumps({
            "useDocOrientationClassify": False,
            "useDocUnwarping": False,
            "useChartRecognition": False,
        }),
    }
    try:
        with path.open("rb") as f:
            files = {"file": f}
            job_response = requests.post(api_url, headers=headers, data=data, files=files, timeout=120)
        _debug_log("paddle-api jobs submit status=", _resp_status(job_response), "url=", api_url)
        _debug_log("paddle-api jobs submit body=", _resp_text(job_response))
        job_response.raise_for_status()
        job_id = job_response.json()["data"]["jobId"]
    except Exception as exc:
        _mark_paddle_failure(exc)
        return ""

    for _ in range(int(os.getenv("XYB_PADDLE_POLL_MAX", "12"))):
        try:
            poll = requests.get(f"{api_url}/{job_id}", headers=headers, timeout=60)
            _debug_log("paddle-api jobs poll status=", _resp_status(poll), "job=", job_id)
            _debug_log("paddle-api jobs poll body=", _resp_text(poll))
            poll.raise_for_status()
            payload = poll.json()["data"]
            state = payload["state"]
        except Exception as exc:
            _mark_paddle_failure(exc)
            _debug_log("paddle-api jobs poll exception=", repr(exc))
            return ""
        if state == "done":
            json_url = payload.get("resultUrl", {}).get("jsonUrl", "")
            if not json_url:
                return ""
            try:
                resp = requests.get(json_url, timeout=120)
                _debug_log("paddle-api jobs json url=", json_url, "status=", _resp_status(resp))
                _debug_log("paddle-api jobs json text=", _resp_text(resp))
                resp.raise_for_status()
            except Exception as exc:
                _mark_paddle_failure(exc)
                _debug_log("paddle-api jobs json exception=", repr(exc))
                return ""
            parts: list[str] = []
            for line in resp.text.strip().splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line).get("result", {})
                except Exception:
                    continue
                for entry in item.get("layoutParsingResults", []) or []:
                    markdown = entry.get("markdown", {}) if isinstance(entry, dict) else {}
                    text = str(markdown.get("text", "")).strip()
                    if text:
                        parts.append(text)
            out = "\n\n".join(parts)
            if out.strip():
                _mark_paddle_success()
            return out
        if state == "failed":
            _mark_paddle_failure(RuntimeError("paddle-api state failed"))
            return ""
        time.sleep(2)
    _mark_paddle_failure(RuntimeError("paddle-api poll timeout"))
    return ""


def _paddle_api_file_type(path: Path) -> int:
    if path.suffix.lower() == ".pdf":
        return 0
    return 1


def _read_image_text_mineru_api(path: Path) -> str:
    base_url = os.getenv("MINERU_API_BASE_URL", "https://mineru.net").rstrip("/")
    token = os.getenv("MINERU_API_TOKEN")
    if not token:
        raise RuntimeError("MinerU API env is missing: MINERU_API_TOKEN")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    try:
        meta_resp = requests.post(
            f"{base_url}/api/v4/file-urls/batch",
            headers=headers,
            json={"enable_formula": False, "language": "ch", "files": [{"name": path.name}]},
            timeout=60,
        )
        _debug_log("mineru-api batch status=", _resp_status(meta_resp), "url=", f"{base_url}/api/v4/file-urls/batch")
        _debug_log("mineru-api batch body=", _resp_text(meta_resp))
        meta_resp.raise_for_status()
        meta_data = meta_resp.json()["data"]
        upload_urls = meta_data.get("file_urls") or meta_data.get("fileUrls") or []
        upload_url = upload_urls[0] if upload_urls else ""
        batch_id = meta_data.get("batch_id") or meta_data.get("batchId", "")
    except Exception as exc:
        _mark_mineru_failure(exc)
        _debug_log("mineru-api batch exception=", repr(exc))
        return ""

    if not upload_url or not batch_id:
        return ""

    try:
        with path.open("rb") as f:
            upload_resp = requests.put(upload_url, data=f, timeout=300)
        _debug_log("mineru-api upload status=", _resp_status(upload_resp), "upload_url=", upload_url[:500])
        if upload_resp.status_code >= 400:
            return ""
    except Exception as exc:
        _mark_mineru_failure(exc)
        _debug_log("mineru-api upload exception=", repr(exc))
        return ""

    status_url = f"{base_url}/api/v4/extract-results/batch/{batch_id}"

    zip_url = ""
    for _ in range(120):
        try:
            poll = requests.get(status_url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
            _debug_log("mineru-api poll status=", _resp_status(poll), "url=", status_url)
            _debug_log("mineru-api poll body=", _resp_text(poll))
            poll.raise_for_status()
            body = poll.json().get("data", {})
        except Exception as exc:
            _mark_mineru_failure(exc)
            _debug_log("mineru-api poll exception=", repr(exc))
            return ""
        extract_results = body.get("extract_result") or body.get("extractResults") or []
        if not extract_results:
            time.sleep(2)
            continue
        target = extract_results[0]
        state = str(target.get("state", "")).lower()
        if state in {"done", "success", "completed"}:
            zip_url = target.get("full_zip_url") or target.get("fullZipUrl") or ""
            break
        if state in {"failed", "error"}:
            return ""
        time.sleep(2)

    if not zip_url:
        return ""

    try:
        with tempfile.TemporaryDirectory(prefix="xyb-mineru-api-") as tmpdir:
            zip_path = Path(tmpdir) / "result.zip"
            resp = requests.get(zip_url, timeout=300)
            _debug_log("mineru-api zip status=", _resp_status(resp), "zip_url=", zip_url)
            resp.raise_for_status()
            zip_path.write_bytes(resp.content)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmpdir)
                _debug_log("mineru-api zip names=", zf.namelist()[:50])
            md_files = sorted(Path(tmpdir).rglob("*.md"))
            texts: list[str] = []
            for md in md_files:
                content = md.read_text(encoding="utf-8", errors="ignore").strip()
                if content:
                    texts.append(content)
            if texts:
                _mark_mineru_success()
                return "\n\n".join(texts)
            json_files = sorted(Path(tmpdir).rglob("*.json"))
            for jf in json_files:
                content = jf.read_text(encoding="utf-8", errors="ignore").strip()
                if content:
                    _mark_mineru_success()
                    return content
    except Exception as exc:
        _mark_mineru_failure(exc)
        _debug_log("mineru-api unzip/read exception=", repr(exc))
        return ""
    return ""


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
