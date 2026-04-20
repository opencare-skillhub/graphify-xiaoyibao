from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from xyb.analyze import god_nodes, surprising_connections, suggest_questions
from xyb.build import build_from_json
from xyb.cluster import cluster, score_all
from xyb.detect import detect, docx_to_markdown, extract_pdf_text, save_manifest, xlsx_to_markdown
from xyb.dicom import dicom_file_node_id, read_dicom_metadata
from xyb.mineru_batch import extract_images_batch
from xyb.ocr import read_image_text
from xyb.normalized import (
    extract_marker_records_from_nodes,
    extract_marker_records_from_texts,
    write_normalized_markers,
)
from xyb.export import to_html, to_json
from xyb.report import generate
from xyb.validation import validate_marker_records, write_validation_outputs


def _id(prefix: str, *parts: str) -> str:
    raw = "::".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha1(raw).hexdigest()[:16]}"


def _labels_for_communities(graph, communities: dict[int, list[str]]) -> dict[int, str]:
    labels: dict[int, str] = {}
    for cid, node_ids in communities.items():
        sample: list[str] = []
        for nid in node_ids[:3]:
            label = graph.nodes[nid].get("label", nid)
            if label not in sample:
                sample.append(label)
        labels[cid] = " / ".join(sample[:3]) if sample else f"Community {cid}"
    return labels


_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "you",
    "are", "was", "were", "been", "has", "have", "had", "not", "but", "can",
    "will", "would", "should", "could", "about", "after", "before", "when",
    "where", "which", "what", "how", "why", "who", "whom", "whose", "then",
    "than", "also", "there", "their", "them", "they", "our", "out", "all",
    "any", "one", "two", "three", "into", "onto", "over", "under", "between",
}

_IMAGE_MARKER_HINTS: list[tuple[str, re.Pattern[str]]] = [
    ("CEA", re.compile(r"\bCEA\b|癌胚抗原", re.I)),
    ("CA125", re.compile(r"糖链抗原125|(?<!\d)125(?!\d)", re.I)),
    ("CA15-3", re.compile(r"糖链抗原15\s*-\s*3|15\s*-\s*3", re.I)),
    ("CA72-4", re.compile(r"糖链抗原72\s*-\s*4|72\s*-\s*4", re.I)),
    ("CA242", re.compile(r"糖链抗原242|(?<!\d)242(?!\d)", re.I)),
    ("CA50", re.compile(r"糖链抗原50|(?<!\d)50(?!\d)", re.I)),
    ("CA19-9", re.compile(r"19\s*-\s*9", re.I)),
    ("AFP", re.compile(r"\bAFP\b", re.I)),
]


def _read_text_content(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            return extract_pdf_text(path)
        if suffix == ".docx":
            return docx_to_markdown(path)
        if suffix == ".xlsx":
            return xlsx_to_markdown(path)
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_concepts(text: str, *, max_terms: int = 20) -> list[str]:
    # 英文 token
    en = [
        t.lower() for t in re.findall(r"[A-Za-z][A-Za-z0-9_\\-]{2,40}", text)
        if t.lower() not in _STOPWORDS
    ]
    # 中文 token（连续 2~10 字）
    zh = re.findall(r"[\u4e00-\u9fff]{2,10}", text)

    freq: dict[str, int] = {}
    for token in en + zh:
        if token.isdigit():
            continue
        freq[token] = freq.get(token, 0) + 1

    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [term for term, _ in ranked[:max_terms]]


def _extract_image_medical_concepts(text: str, *, max_terms: int = 20) -> list[str]:
    """从图片 OCR 文本提取医学相关概念，避免纯噪声 token。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    results: list[str] = []

    # 1) 肿瘤标志物结构化解析：优先取“结果值”，避免把参考值当结果
    value_re = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(ng/ml|u/ml|iu/ml|u/mi|U/mi|U/mL|ng/mL|IU/mL)", re.I)
    marker_values: dict[str, str] = {}
    pending_marker: str | None = None

    def _norm_unit(unit: str) -> str:
        return (
            unit.replace("U/mi", "U/mL")
            .replace("u/mi", "U/mL")
            .replace("u/ml", "U/mL")
            .replace("U/ml", "U/mL")
            .replace("ng/ml", "ng/mL")
        )

    for line in lines:
        if pending_marker:
            # 纯结果数值行优先绑定到上一个 marker
            compact_line = line.replace(" ", "")
            mv_direct = value_re.fullmatch(compact_line)
            if mv_direct:
                marker_values[pending_marker] = f"{mv_direct.group(1)} {_norm_unit(mv_direct.group(2))}"
                pending_marker = None
                continue

        marker_label = None
        for mk, pat in _IMAGE_MARKER_HINTS:
            if pat.search(line):
                marker_label = mk
                break

        if marker_label:
            pending_marker = marker_label
            # 行内如果直接带结果值，先取第一个；若同一行还含“参考值”，后续会被更精确结果覆盖
            values = value_re.findall(line)
            if values:
                val, unit = values[0]
                marker_values[marker_label] = f"{val} {_norm_unit(unit)}"
            continue

        if pending_marker:
            # 跳过参考值行
            if "参考值" in line or "0-" in line or "0.00-" in line:
                continue
            mv = value_re.search(line)
            if mv:
                marker_values[pending_marker] = f"{mv.group(1)} {_norm_unit(mv.group(2))}"
                pending_marker = None
                continue
            # 单独数值行（如 OCR 把单位拆开），也尝试接收
            mv_num = re.search(r"([0-9]+(?:\.[0-9]+)?)", line)
            if mv_num and ("参考值" not in line):
                marker_values[pending_marker] = mv_num.group(1)
                pending_marker = None
                continue

    for mk in ["CEA", "CA125", "CA15-3", "CA72-4", "CA242", "CA50", "CA19-9", "AFP"]:
        if mk in marker_values:
            results.append(f"{mk} {marker_values[mk]}")
        elif any(pat.search(joined := '\n'.join(lines)) for name, pat in _IMAGE_MARKER_HINTS if name == mk):
            results.append(mk)

    # 2) 影像相关关键词
    imaging_terms = [
        ("CT", re.compile(r"\bCT\b|增强CT|复查CT|影像", re.I)),
        ("放射学诊断", re.compile(r"放射学诊断", re.I)),
        ("PET-CT", re.compile(r"PET\s*-\s*CT|PETCT", re.I)),
        ("病灶", re.compile(r"病灶|结节|占位", re.I)),
        ("转移", re.compile(r"转移|播散", re.I)),
        ("胰头", re.compile(r"胰头", re.I)),
        ("肝脏", re.compile(r"肝|肝脏", re.I)),
        ("肝包膜", re.compile(r"肝包膜", re.I)),
        ("腹膜", re.compile(r"腹膜", re.I)),
        ("胆囊结石", re.compile(r"胆囊结石|结石", re.I)),
    ]
    joined = "\n".join(lines)
    for label, pat in imaging_terms:
        if pat.search(joined):
            results.append(label)

    # 3) 日期信息
    for m in re.finditer(r"(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2})", joined):
        results.append(m.group(1))

    # 去重保序
    dedup: list[str] = []
    seen: set[str] = set()
    for item in results:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)
        if len(dedup) >= max_terms:
            break
    return dedup


def _normalize_file_type(raw: str) -> str:
    ft = (raw or "").lower().strip()
    if ft in {"document", "paper", "image", "video", "dicom", "rationale"}:
        return ft
    if ft in {"pdf"}:
        return "paper"
    if ft in {"png", "jpg", "jpeg", "gif", "webp", "svg", "heic", "heif"}:
        return "image"
    if ft in {"mp4", "mov", "webm", "mkv", "avi", "m4v", "mp3", "wav", "m4a", "ogg"}:
        return "video"
    if ft in {"dcm", "dicom"}:
        return "dicom"
    return "document"


def _norm_source_file(value) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _normalize_node(node: dict) -> dict:
    n = dict(node)
    n.setdefault("id", _id("node", str(n.get("label", "")), _norm_source_file(n.get("source_file", ""))))
    n.setdefault("label", str(n.get("id", "")))
    n["file_type"] = _normalize_file_type(str(n.get("file_type", n.get("kind", "document"))))
    n["source_file"] = _norm_source_file(n.get("source_file", ""))
    n.setdefault("source_location", "")
    return n


def _normalize_edge(edge: dict) -> dict:
    e = dict(edge)
    if "source" not in e and "from" in e:
        e["source"] = e["from"]
    if "target" not in e and "to" in e:
        e["target"] = e["to"]
    e.setdefault("relation", "related_to")
    e.setdefault("confidence", "INFERRED")
    e["source_file"] = _norm_source_file(e.get("source_file", ""))
    e.setdefault("source_location", "")
    e.setdefault("weight", 1.0)
    return e


def _load_graphify_standard_chunks(root: Path) -> tuple[list[dict], list[dict], list[dict]]:
    chunk_dir = root / "graphify-out"
    if not chunk_dir.exists():
        return [], [], []
    nodes: list[dict] = []
    edges: list[dict] = []
    hyperedges: list[dict] = []
    chunk_files = sorted(chunk_dir.glob(".graphify_standard_chunk_*.json")) + sorted(
        chunk_dir.glob(".graphify_chunk_*.json")
    )
    for chunk in chunk_files:
        try:
            payload = json.loads(chunk.read_text(encoding="utf-8"))
        except Exception:
            continue
        for n in payload.get("nodes", []):
            if not isinstance(n, dict):
                continue
            nodes.append(_normalize_node(n))
        for e in payload.get("edges", []):
            if not isinstance(e, dict):
                continue
            edges.append(_normalize_edge(e))
        for h in payload.get("hyperedges", []):
            if isinstance(h, dict):
                hyperedges.append(dict(h))
    return nodes, edges, hyperedges


def _load_graphify_semantic_pipeline(root: Path) -> tuple[list[dict], list[dict], list[dict]]:
    out = root / "graphify-out"
    semantic_path = out / ".graphify_semantic.json"
    if not semantic_path.exists():
        return [], [], []

    try:
        semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
    except Exception:
        return [], [], []

    ast_path = out / ".graphify_ast.json"
    try:
        ast = json.loads(ast_path.read_text(encoding="utf-8")) if ast_path.exists() else {"nodes": [], "edges": []}
    except Exception:
        ast = {"nodes": [], "edges": []}

    ordered_nodes: list[dict] = []
    for n in ast.get("nodes", []):
        if isinstance(n, dict):
            ordered_nodes.append(_normalize_node(n))
    for n in semantic.get("nodes", []):
        if isinstance(n, dict):
            ordered_nodes.append(_normalize_node(n))

    # 与 graphify build(ast -> semantic) 一致：同 ID 语义节点覆盖 AST 节点
    node_map: dict[str, dict] = {}
    for n in ordered_nodes:
        node_map[str(n["id"])] = n
    nodes = list(node_map.values())
    node_ids = {n["id"] for n in nodes}

    edges: list[dict] = []
    for e in ast.get("edges", []):
        if not isinstance(e, dict):
            continue
        ee = _normalize_edge(e)
        if ee.get("source") in node_ids and ee.get("target") in node_ids:
            edges.append(ee)
    for e in semantic.get("edges", []):
        if not isinstance(e, dict):
            continue
        ee = _normalize_edge(e)
        if ee.get("source") in node_ids and ee.get("target") in node_ids:
            edges.append(ee)

    hyperedges = [dict(h) for h in semantic.get("hyperedges", []) if isinstance(h, dict)]
    return nodes, edges, hyperedges


def process_path(
    path: Path,
    *,
    output_dir: Path,
    follow_symlinks: bool = False,
    ocr_backend: str = "auto",
    retry_failed_only: bool = False,
) -> dict:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "process.log"
    summary_file = output_dir / "process_result.json"
    process_failure_file = output_dir / "process_failures.jsonl"

    def _log(level: str, msg: str, **fields: object) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "msg": msg,
            **fields,
        }
        try:
            with log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

    progress_cfg = os.getenv("XYB_PROGRESS", "auto").strip().lower()
    if progress_cfg in {"0", "false", "off", "no"}:
        progress_on = False
    elif progress_cfg in {"1", "true", "on", "yes"}:
        progress_on = True
    else:
        progress_on = sys.stderr.isatty()
    progress_dynamic = bool(progress_on and sys.stderr.isatty())
    progress_last_ts = 0.0

    def _progress(msg: str, *, done: int | None = None, total: int | None = None, final: bool = False) -> None:
        nonlocal progress_last_ts
        _log("INFO", "progress", stage=msg, done=done, total=total, final=final)
        if not progress_on:
            return
        now = time.time()
        # 限流，避免刷屏；final 强制输出
        if not final and now - progress_last_ts < 0.08:
            return
        progress_last_ts = now
        prefix = "[xyb]"
        if done is not None and total:
            pct = int(done * 100 / max(total, 1))
            line = f"{prefix} {msg} {done}/{total} ({pct}%)"
        else:
            line = f"{prefix} {msg}"
        if progress_dynamic:
            end = "\n" if final else ""
            print(f"\r{line}", end=end, file=sys.stderr, flush=True)
        else:
            # 非 TTY 时降级为阶段日志，避免看起来“卡住”
            if done is not None and total and not final and done not in {1, total} and done % 50 != 0:
                return
            print(line, file=sys.stderr, flush=True)

    _log("INFO", "process start", root=str(path), output_dir=str(output_dir), ocr_backend=ocr_backend)
    _progress("detecting files...")
    detection = detect(path, follow_symlinks=follow_symlinks)
    total_files = sum(len(v) for v in detection.get("files", {}).values())
    _progress("loading graphify semantic pipeline...")
    imported_nodes, imported_edges, imported_hyperedges = _load_graphify_semantic_pipeline(path)
    if not imported_nodes:
        _progress("loading graphify standard chunks...")
        imported_nodes, imported_edges, imported_hyperedges = _load_graphify_standard_chunks(path)
    use_graphify_extract = bool(imported_nodes)

    by_source_file: dict[str, list[str]] = {}
    for n in imported_nodes:
        sf = _norm_source_file(n.get("source_file", ""))
        if sf:
            by_source_file.setdefault(sf, []).append(n["id"])
    covered_files = set(by_source_file.keys())

    image_text_by_file: dict[str, str] = {}
    mineru_failures: list[dict] = []
    failure_file = output_dir / "ocr_failures_mineru.jsonl"
    retry_failed = os.getenv("XYB_RETRY_FAILED", "1").strip().lower() not in {"0", "false", "off", "no"}
    previous_failures: dict[str, dict] = {}
    if failure_file.exists():
        try:
            for ln in failure_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not ln.strip():
                    continue
                obj = json.loads(ln)
                sf = str(obj.get("source_file", ""))
                if sf:
                    previous_failures[sf] = obj
        except Exception:
            previous_failures = {}
    if ocr_backend in {"auto", "mineru-api"}:
        if retry_failed_only:
            image_files = []
        else:
            image_files = [Path(f) for f in detection.get("files", {}).get("image", [])]
        if (retry_failed or retry_failed_only) and previous_failures:
            try:
                for sf, obj in previous_failures.items():
                    if bool(obj.get("give_up")):
                        continue
                    if sf and Path(sf).exists():
                        image_files.append(Path(sf))
            except Exception:
                pass
        # 去重保序
        uniq: list[Path] = []
        seen: set[str] = set()
        for p in image_files:
            ps = str(p)
            if ps in seen:
                continue
            seen.add(ps)
            uniq.append(p)
        image_files = uniq
        if image_files:
            _progress("mineru batch extracting images...")
            image_text_by_file, mineru_failures = extract_images_batch(image_files)
            # 执行中自动补跑 1~2 轮（可配），用于网络抖动导致的下载/轮询失败
            retry_rounds = max(0, int(os.getenv("XYB_MINERU_RETRY_ROUNDS", "2")))
            for r in range(retry_rounds):
                if not mineru_failures:
                    break
                retry_paths: list[Path] = []
                seen_retry: set[str] = set()
                for item in mineru_failures:
                    sf = str(item.get("source_file", ""))
                    if sf and sf not in seen_retry and Path(sf).exists():
                        seen_retry.add(sf)
                        retry_paths.append(Path(sf))
                if not retry_paths:
                    break
                _progress(f"mineru retry round {r + 1}/{retry_rounds}...")
                retry_texts, retry_failures = extract_images_batch(retry_paths)
                image_text_by_file.update(retry_texts)
                mineru_failures = retry_failures

    root_id = _id("root", str(path.resolve()))
    nodes: list[dict] = list(imported_nodes)
    edges: list[dict] = list(imported_edges)
    file_texts_for_norm: list[tuple[str, str]] = []
    if not use_graphify_extract:
        nodes.append({
            "id": root_id,
            "label": path.name or str(path),
            "file_type": "document",
            "source_file": str(path),
            "source_location": "",
        })

    processed = 0
    file_success = 0
    file_failures: list[dict] = []
    for ftype, files in detection.get("files", {}).items():
        for f in files:
            processed += 1
            _progress(f"processing {ftype}", done=processed, total=total_files)
            p = Path(f)
            file_key = str(p)
            try:
                existing_ids = by_source_file.get(file_key, [])
                if existing_ids:
                    if not use_graphify_extract:
                        edges.append({
                            "source": root_id,
                            "target": existing_ids[0],
                            "relation": "contains",
                            "confidence": "EXTRACTED",
                            "source_file": str(path),
                            "source_location": "",
                            "weight": 1.0,
                        })
                else:
                    file_id = dicom_file_node_id(p) if ftype == "dicom" else _id("file", str(p.resolve()))
                    nodes.append({
                        "id": file_id,
                        "label": p.stem,
                        "file_type": ftype,
                        "source_file": file_key,
                        "source_location": "",
                    })
                    if not use_graphify_extract:
                        edges.append({
                            "source": root_id,
                            "target": file_id,
                            "relation": "contains",
                            "confidence": "EXTRACTED",
                            "source_file": str(path),
                            "source_location": "",
                            "weight": 1.0,
                        })
                    by_source_file.setdefault(file_key, []).append(file_id)
                    covered_files.add(file_key)

                if ftype != "dicom":
                    if file_key in covered_files and existing_ids:
                        # graphify 产物已覆盖该文件，避免重复生成大量弱关系
                        file_success += 1
                        continue
                    if ftype in {"document", "paper"}:
                        text = _read_text_content(p)
                    elif ftype == "image":
                        text = image_text_by_file.get(str(p), "")
                        if not text:
                            text = read_image_text(p, backend=ocr_backend)
                    else:
                        text = ""
                    if text.strip():
                        file_texts_for_norm.append((str(p), text))
                    # 统一抽取链：图片/文档都走同一概念提取流程。
                    # 图片文本在 auto 模式下优先由 multimodal backend 提供，
                    # OCR 仅在多模态不可用时作为 fallback。
                    concepts = _extract_concepts(text) if text.strip() else []
                    concept_ids: list[str] = []
                    file_id = by_source_file.get(file_key, [""])[0]
                    for c in concepts:
                        cid = _id("concept", c)
                        concept_ids.append(cid)
                        nodes.append({
                            "id": cid,
                            "label": c,
                            "file_type": "rationale",
                            "source_file": str(p),
                            "source_location": "",
                        })
                        edges.append({
                            "source": file_id,
                            "target": cid,
                            "relation": "mentions",
                            "confidence": "INFERRED",
                            "source_file": str(p),
                            "source_location": "",
                            "weight": 1.0,
                        })
                    # 同文件概念共现关系（轻量）
                    for i in range(len(concept_ids)):
                        for j in range(i + 1, min(i + 4, len(concept_ids))):
                            edges.append({
                                "source": concept_ids[i],
                                "target": concept_ids[j],
                                "relation": "co_occurs_with",
                                "confidence": "INFERRED",
                                "source_file": str(p),
                                "source_location": "",
                                "weight": 0.5,
                            })
                    file_success += 1
                    continue

                file_id = by_source_file.get(file_key, [""])[0]
                for key, value in read_dicom_metadata(p).items():
                    meta_id = _id("dicom_meta", file_id, key, value)
                    nodes.append({
                        "id": meta_id,
                        "label": f"{key}: {value}",
                        "file_type": "rationale",
                        "source_file": str(p),
                        "source_location": "",
                    })
                    edges.append({
                        "source": file_id,
                        "target": meta_id,
                        "relation": "has_metadata",
                        "confidence": "EXTRACTED",
                        "source_file": str(p),
                        "source_location": "",
                        "weight": 1.0,
                    })
                file_success += 1
            except Exception as exc:
                fail_item = {
                    "source_file": str(p),
                    "file_type": ftype,
                    "stage": "process-file",
                    "error": repr(exc),
                }
                file_failures.append(fail_item)
                _log("ERROR", "file process failed", **fail_item)
                continue

    _progress("building extraction payload...")
    extraction = {
        "nodes": list({n["id"]: n for n in nodes}.values()),
        "edges": list({
            (e["source"], e["target"], e["relation"], e.get("source_file", "")): e
            for e in edges
            if e.get("source") and e.get("target")
        }.values()),
        "hyperedges": imported_hyperedges,
        "input_tokens": 0,
        "output_tokens": 0,
    }

    (output_dir / ".graphify_extract.json").write_text(
        json.dumps(extraction, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / ".graphify_detect.json").write_text(
        json.dumps(detection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 写入增量基线清单，供 detect_incremental 比较新增/修改/删除文件
    save_manifest(detection.get("files", {}), str(output_dir / "manifest.json"))

    current_files = {f for fl in detection.get("files", {}).values() for f in fl}
    _progress("extracting marker records...")
    text_marker_records = extract_marker_records_from_texts(file_texts_for_norm)
    node_marker_records = extract_marker_records_from_nodes(extraction["nodes"])
    # 以文本直抽为主（更能区分“结果值 vs 参考范围”），节点抽取仅补充文本未覆盖文件
    text_sources = {str(r.get("source_file", "")) for r in text_marker_records}
    marker_records = list(text_marker_records)
    marker_records += [r for r in node_marker_records if str(r.get("source_file", "")) not in text_sources]
    write_normalized_markers(output_dir, marker_records, current_files)
    _progress("validating marker records...")
    validated_rows, validation_conflicts, review_queue, validation_summary = validate_marker_records(
        marker_records,
        progress_cb=lambda i, t: _progress("validating", done=i, total=t),
    )
    validation_output = write_validation_outputs(
        output_dir,
        validated_rows,
        validation_conflicts,
        review_queue,
        validation_summary,
    )
    # 失败文件追踪：主流程继续，失败文件落盘用于补跑收敛
    if mineru_failures:
        give_up_after = max(1, int(os.getenv("XYB_MINERU_GIVEUP_AFTER", "6")))
        now_iso = datetime.now(timezone.utc).isoformat()
        with failure_file.open("w", encoding="utf-8") as f:
            for item in mineru_failures:
                sf = str(item.get("source_file", ""))
                prev = previous_failures.get(sf, {})
                retry_count = int(prev.get("retry_count", 0)) + 1
                item["retry_count"] = retry_count
                item["last_retry_at"] = now_iso
                item["first_failed_at"] = prev.get("first_failed_at", now_iso)
                item["give_up"] = retry_count >= give_up_after
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
    else:
        if failure_file.exists():
            failure_file.unlink(missing_ok=True)
    if file_failures:
        with process_failure_file.open("w", encoding="utf-8") as f:
            for item in file_failures:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
    elif process_failure_file.exists():
        process_failure_file.unlink(missing_ok=True)

    _progress("building graph...")
    graph = build_from_json(extraction)
    _progress("clustering communities...")
    communities = cluster(graph)
    cohesion = score_all(graph, communities)
    labels = _labels_for_communities(graph, communities)
    gods = god_nodes(graph)
    surprises = surprising_connections(graph, communities)
    questions = suggest_questions(graph, communities, labels)

    _progress("exporting graph artifacts...")
    to_json(graph, communities, str(output_dir / "graph.json"))
    if graph.number_of_nodes() <= 5000:
        to_html(graph, communities, str(output_dir / "graph.html"), community_labels=labels)

    _progress("generating report...")
    report_text = generate(
        graph,
        communities=communities,
        cohesion_scores=cohesion,
        community_labels=labels,
        god_node_list=gods,
        surprise_list=surprises,
        detection_result=detection,
        token_cost={"input": 0, "output": 0},
        root=str(path),
        suggested_questions=questions,
    )
    (output_dir / "GRAPH_REPORT.md").write_text(report_text, encoding="utf-8")

    _progress("done", done=total_files, total=total_files, final=True)
    result = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "communities": len(communities),
        "output_dir": str(output_dir.resolve()),
        "dicom_count": len(detection.get("files", {}).get("dicom", [])),
        "ocr_failures": len(mineru_failures),
        "ocr_failure_file": str(failure_file.resolve()) if mineru_failures else None,
        "conversion": {
            "total_files": total_files,
            "success_files": file_success,
            "failed_files": len(file_failures),
            "failed_file_list": str(process_failure_file.resolve()) if file_failures else None,
        },
        "validation": validation_output,
        "log_file": str(log_file.resolve()),
    }
    summary_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["result_file"] = str(summary_file.resolve())
    _log(
        "INFO",
        "process done",
        total_files=total_files,
        success_files=file_success,
        failed_files=len(file_failures),
        ocr_failures=len(mineru_failures),
        log_file=str(log_file.resolve()),
        result_file=str(summary_file.resolve()),
    )
    return result
