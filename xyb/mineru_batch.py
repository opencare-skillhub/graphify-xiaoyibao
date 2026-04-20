from __future__ import annotations

import io
import json
import os
import time
import zipfile
from pathlib import Path

import requests


def _debug_enabled() -> bool:
    return os.getenv("XYB_OCR_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _debug(*parts) -> None:
    if _debug_enabled():
        try:
            print("[xyb-mineru-batch]", *parts)
        except Exception:
            pass


def _request_with_retry(method: str, url: str, *, retries: int = 3, backoff: float = 1.5, **kwargs):
    last_exc: Exception | None = None
    for i in range(retries):
        try:
            return requests.request(method, url, **kwargs)
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            _debug("request retry", method, url, f"{i+1}/{retries}", repr(exc))
            if i < retries - 1:
                time.sleep(backoff * (i + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError("request failed without exception")


def _extract_text_from_zip_bytes(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()
            _debug("zip names", names[:10])
            json_names = [n for n in names if n.lower().endswith(".json")]
            # 优先 content_list/layout 的结构化文本（比 full.md 更稳，减少表格错位）
            for n in json_names:
                if "content_list" not in n and "layout" not in n:
                    continue
                text = zf.read(n).decode("utf-8", errors="ignore").strip()
                structured = _mineru_structured_text_from_json(text)
                if structured:
                    return structured
            md_names = [n for n in names if n.lower().endswith(".md")]
            for n in md_names:
                text = zf.read(n).decode("utf-8", errors="ignore").strip()
                if text:
                    return text
            for n in json_names:
                text = zf.read(n).decode("utf-8", errors="ignore").strip()
                if text:
                    return text
    except Exception as exc:  # pragma: no cover
        _debug("zip parse error", repr(exc))
    return ""


def _mineru_structured_text_from_json(raw: str) -> str:
    if not raw.strip():
        return ""
    try:
        obj = json.loads(raw)
    except Exception:
        return ""

    entries: list[tuple[int, float, float, str]] = []

    def _add_item(page: int, bbox, text: str) -> None:
        if not text or not isinstance(bbox, list) or len(bbox) < 4:
            return
        try:
            x1, y1, x2, y2 = map(float, bbox[:4])
            yc = (y1 + y2) / 2.0
            entries.append((int(page), yc, x1, str(text).strip()))
        except Exception:
            return

    if isinstance(obj, list):
        for item in obj:
            if not isinstance(item, dict):
                continue
            _add_item(int(item.get("page_idx", 0)), item.get("bbox"), str(item.get("text", "")).strip())
    elif isinstance(obj, dict):
        pdf_info = obj.get("pdf_info", [])
        if isinstance(pdf_info, list):
            for page_idx, page in enumerate(pdf_info):
                if not isinstance(page, dict):
                    continue
                for block in page.get("preproc_blocks", []) if isinstance(page.get("preproc_blocks"), list) else []:
                    if not isinstance(block, dict):
                        continue
                    if "text" in block:
                        _add_item(page_idx, block.get("bbox"), str(block.get("text", "")).strip())
                        continue
                    lines = block.get("lines", [])
                    if not isinstance(lines, list):
                        continue
                    for ln in lines:
                        if not isinstance(ln, dict):
                            continue
                        spans = ln.get("spans", [])
                        if not isinstance(spans, list):
                            continue
                        text = "".join(str(sp.get("content", "")) for sp in spans if isinstance(sp, dict)).strip()
                        _add_item(page_idx, ln.get("bbox"), text)

    if not entries:
        return ""
    by_page: dict[int, list[tuple[int, float, float, str]]] = {}
    for e in entries:
        by_page.setdefault(e[0], []).append(e)

    panel_entries: list[tuple[int, int, float, float, str]] = []
    has_multi_panel = False
    for page, items in by_page.items():
        xs = sorted(e[2] for e in items)
        split_x: float | None = None
        if len(xs) >= 8:
            gaps = [(xs[i + 1] - xs[i], i) for i in range(len(xs) - 1)]
            if gaps:
                best_gap, idx = max(gaps, key=lambda x: x[0])
                if best_gap >= 220:
                    split_x = (xs[idx] + xs[idx + 1]) / 2.0
                    has_multi_panel = True
        for _p, y, x, text in items:
            panel = 1 if split_x is None or x < split_x else 2
            panel_entries.append((page, panel, y, x, text))

    panel_entries.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    y_tol = 14.0
    out_lines: list[str] = []
    cur_page, cur_panel, cur_y, _x, first_text = panel_entries[0]
    cur_parts = [first_text]
    if has_multi_panel:
        out_lines.append(f"[[PANEL:{cur_panel}]]")
    for page, panel, y, _x, text in panel_entries[1:]:
        if page != cur_page or panel != cur_panel:
            line = " ".join(p for p in cur_parts if p).strip()
            if line:
                out_lines.append(line)
            cur_page, cur_panel, cur_y = page, panel, y
            cur_parts = [text]
            if has_multi_panel:
                out_lines.append(f"[[PANEL:{cur_panel}]]")
            continue
        if abs(y - cur_y) > y_tol:
            line = " ".join(p for p in cur_parts if p).strip()
            if line:
                out_lines.append(line)
            cur_y = y
            cur_parts = [text]
        else:
            cur_parts.append(text)
    line = " ".join(p for p in cur_parts if p).strip()
    if line:
        out_lines.append(line)
    return "\n".join(out_lines).strip()


def extract_images_batch(image_paths: list[Path]) -> tuple[dict[str, str], list[dict]]:
    """
    MinerU 精准 API 批量解析：
    - 申请批量上传 URL
    - 批量上传
    - 轮询批次结果
    - 下载 zip 并提取文本
    """
    token = os.getenv("MINERU_API_TOKEN", "").strip()
    if not token:
        return {}
    base_url = os.getenv("MINERU_API_BASE_URL", "https://mineru.net").rstrip("/")
    batch_size = max(1, int(os.getenv("XYB_MINERU_BATCH_SIZE", "32")))
    poll_max = max(1, int(os.getenv("XYB_MINERU_POLL_MAX", "120")))
    poll_sleep = max(1, int(os.getenv("XYB_MINERU_POLL_SLEEP", "2")))

    out: dict[str, str] = {}
    failures: list[dict] = []
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    for idx in range(0, len(image_paths), batch_size):
        chunk = image_paths[idx: idx + batch_size]
        files_payload = [{"name": p.name, "data_id": str(p)} for p in chunk]
        try:
            resp = _request_with_retry(
                "POST",
                f"{base_url}/api/v4/file-urls/batch",
                headers=headers,
                json={"enable_formula": False, "language": "ch", "files": files_payload},
                timeout=60,
                retries=3,
            )
            resp.raise_for_status()
            body = resp.json().get("data", {})
            batch_id = body.get("batch_id") or body.get("batchId") or ""
            file_urls = body.get("file_urls") or body.get("fileUrls") or []
        except Exception as exc:  # pragma: no cover
            _debug("create batch failed", repr(exc))
            for p in chunk:
                failures.append({
                    "source_file": str(p),
                    "stage": "create_batch",
                    "error": repr(exc),
                })
            continue

        if not batch_id or len(file_urls) != len(chunk):
            _debug("invalid batch payload", batch_id, len(file_urls), len(chunk))
            for p in chunk:
                failures.append({
                    "source_file": str(p),
                    "stage": "create_batch_invalid",
                    "error": f"batch_id={batch_id}, urls={len(file_urls)}, files={len(chunk)}",
                })
            continue

        # 上传
        for p, upload_url in zip(chunk, file_urls):
            try:
                with p.open("rb") as f:
                    up = _request_with_retry("PUT", upload_url, data=f, timeout=300, retries=3)
                if up.status_code >= 400:
                    _debug("upload failed", p, up.status_code)
                    failures.append({
                        "source_file": str(p),
                        "stage": "upload",
                        "error": f"status={up.status_code}",
                        "batch_id": batch_id,
                    })
            except Exception as exc:  # pragma: no cover
                _debug("upload exception", p, repr(exc))
                failures.append({
                    "source_file": str(p),
                    "stage": "upload",
                    "error": repr(exc),
                    "batch_id": batch_id,
                })

        # 轮询
        result_items: list[dict] = []
        status_url = f"{base_url}/api/v4/extract-results/batch/{batch_id}"
        for _ in range(poll_max):
            try:
                poll = _request_with_retry(
                    "GET",
                    status_url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=60,
                    retries=2,
                )
                poll.raise_for_status()
                data = poll.json().get("data", {})
                items = data.get("extract_result") or data.get("extractResults") or []
                if items:
                    result_items = items
                all_done = bool(items) and all(
                    str(it.get("state", "")).lower() in {"done", "success", "completed", "failed", "error"}
                    for it in items
                )
                if all_done:
                    break
            except Exception as exc:  # pragma: no cover
                _debug("poll exception", repr(exc))
            time.sleep(poll_sleep)

        # 下载结果
        resolved_files: set[str] = set()
        for it in result_items:
            state = str(it.get("state", "")).lower()
            if state not in {"done", "success", "completed"}:
                data_id = str(it.get("data_id") or it.get("dataId") or "")
                if data_id:
                    failures.append({
                        "source_file": data_id,
                        "stage": "result_state",
                        "error": f"state={state}",
                        "batch_id": batch_id,
                    })
                continue
            data_id = str(it.get("data_id") or it.get("dataId") or "")
            file_name = str(it.get("file_name") or it.get("fileName") or "")
            zip_url = str(it.get("full_zip_url") or it.get("fullZipUrl") or "")
            if not zip_url:
                if data_id:
                    failures.append({
                        "source_file": data_id,
                        "stage": "result_zip",
                        "error": "empty full_zip_url",
                        "batch_id": batch_id,
                    })
                continue
            try:
                z = _request_with_retry("GET", zip_url, timeout=300, retries=3)
                z.raise_for_status()
                text = _extract_text_from_zip_bytes(z.content)
                if not text:
                    if data_id:
                        failures.append({
                            "source_file": data_id,
                            "stage": "result_parse",
                            "error": "empty text after unzip",
                            "batch_id": batch_id,
                        })
                    continue
                if data_id:
                    out[data_id] = text
                    resolved_files.add(data_id)
                elif file_name:
                    # 兜底匹配
                    for p in chunk:
                        if p.name == file_name:
                            out[str(p)] = text
                            resolved_files.add(str(p))
                            break
            except Exception as exc:  # pragma: no cover
                _debug("download result exception", repr(exc))
                if data_id:
                    failures.append({
                        "source_file": data_id,
                        "stage": "result_download",
                        "error": repr(exc),
                        "batch_id": batch_id,
                    })
                continue

        for p in chunk:
            ps = str(p)
            if ps not in resolved_files and ps not in out:
                # 没在 extract_result 中成功落文本，也没记录过明确失败时，做兜底失败记录
                if not any(f.get("source_file") == ps and f.get("batch_id") == batch_id for f in failures):
                    failures.append({
                        "source_file": ps,
                        "stage": "result_missing",
                        "error": "no successful result mapped",
                        "batch_id": batch_id,
                    })

    # 同一文件可能多次失败，最终仅保留最后一次失败原因
    dedup_fail: dict[str, dict] = {}
    for f in failures:
        dedup_fail[str(f.get("source_file", ""))] = f
    final_failures = [v for k, v in dedup_fail.items() if k and k not in out]
    return out, final_failures
