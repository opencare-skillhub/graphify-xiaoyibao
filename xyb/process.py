from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from xyb.analyze import god_nodes, surprising_connections, suggest_questions
from xyb.build import build_from_json
from xyb.cluster import cluster, score_all
from xyb.detect import detect, docx_to_markdown, extract_pdf_text, xlsx_to_markdown
from xyb.dicom import dicom_file_node_id, read_dicom_metadata
from xyb.export import to_html, to_json
from xyb.report import generate


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
    ("CA19-9", re.compile(r"19\s*-\s*9", re.I)),
    ("CA125", re.compile(r"(?<!\d)125(?!\d)", re.I)),
    ("CA15-3", re.compile(r"15\s*-\s*3", re.I)),
    ("CA72-4", re.compile(r"72\s*-\s*4", re.I)),
    ("CA242", re.compile(r"242", re.I)),
    ("CA50", re.compile(r"(?<!\d)50(?!\d)", re.I)),
    ("CEA", re.compile(r"\bCEA\b", re.I)),
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


def _read_image_text(path: Path) -> str:
    """Best-effort OCR for image files using local tesseract."""
    if shutil.which("tesseract") is None:
        return ""
    src = path
    tmp_png: Path | None = None
    try:
        if path.suffix.lower() in {".heic", ".heif"} and shutil.which("sips"):
            fd, name = tempfile.mkstemp(suffix=".png")
            Path(name).unlink(missing_ok=True)
            subprocess.run(["sips", "-s", "format", "png", str(path), "--out", name], check=False, capture_output=True)
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


def _extract_concepts(text: str, *, max_terms: int = 20) -> list[str]:
    # 英文 token
    en = [
        t.lower() for t in re.findall(r"[A-Za-z][A-Za-z0-9_\\-]{2,40}", text)
        if t.lower() not in _STOPWORDS
    ]
    # 中文 token（连续 2~10 字）
    zh = re.findall(r"[\\u4e00-\\u9fff]{2,10}", text)

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

    # 1) 肿瘤标志物 line 解析
    value_re = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(ng/ml|u/ml|iu/ml|u/mi|U/mi|U/mL|ng/mL)", re.I)
    for line in lines:
        marker_label = None
        for mk, pat in _IMAGE_MARKER_HINTS:
            if pat.search(line):
                marker_label = mk
                break
        if not marker_label:
            continue
        mv = value_re.search(line)
        if mv:
            unit = mv.group(2).replace("U/mi", "U/mL").replace("u/mi", "U/mL")
            results.append(f"{marker_label} {mv.group(1)} {unit}")
        else:
            results.append(marker_label)

    # 2) 影像相关关键词
    imaging_terms = [
        ("CT", re.compile(r"\bCT\b|增强CT|复查CT|影像", re.I)),
        ("PET-CT", re.compile(r"PET\s*-\s*CT|PETCT", re.I)),
        ("病灶", re.compile(r"病灶|结节|占位", re.I)),
        ("转移", re.compile(r"转移|播散", re.I)),
        ("肝脏", re.compile(r"肝|肝脏", re.I)),
        ("腹膜", re.compile(r"腹膜", re.I)),
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


def process_path(path: Path, *, output_dir: Path, follow_symlinks: bool = False) -> dict:
    detection = detect(path, follow_symlinks=follow_symlinks)
    imported_nodes, imported_edges, imported_hyperedges = _load_graphify_semantic_pipeline(path)
    if not imported_nodes:
        imported_nodes, imported_edges, imported_hyperedges = _load_graphify_standard_chunks(path)
    use_graphify_extract = bool(imported_nodes)

    by_source_file: dict[str, list[str]] = {}
    for n in imported_nodes:
        sf = _norm_source_file(n.get("source_file", ""))
        if sf:
            by_source_file.setdefault(sf, []).append(n["id"])
    covered_files = set(by_source_file.keys())

    root_id = _id("root", str(path.resolve()))
    nodes: list[dict] = list(imported_nodes)
    edges: list[dict] = list(imported_edges)
    if not use_graphify_extract:
        nodes.append({
            "id": root_id,
            "label": path.name or str(path),
            "file_type": "document",
            "source_file": str(path),
            "source_location": "",
        })

    for ftype, files in detection.get("files", {}).items():
        for f in files:
            p = Path(f)
            file_key = str(p)
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
                    continue
                if ftype in {"document", "paper"}:
                    text = _read_text_content(p)
                elif ftype == "image":
                    text = _read_image_text(p)
                else:
                    text = ""
                if ftype == "image":
                    concepts = _extract_image_medical_concepts(text) if text.strip() else []
                else:
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

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".graphify_extract.json").write_text(
        json.dumps(extraction, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / ".graphify_detect.json").write_text(
        json.dumps(detection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    graph = build_from_json(extraction)
    communities = cluster(graph)
    cohesion = score_all(graph, communities)
    labels = _labels_for_communities(graph, communities)
    gods = god_nodes(graph)
    surprises = surprising_connections(graph, communities)
    questions = suggest_questions(graph, communities, labels)

    to_json(graph, communities, str(output_dir / "graph.json"))
    if graph.number_of_nodes() <= 5000:
        to_html(graph, communities, str(output_dir / "graph.html"), community_labels=labels)

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

    return {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "communities": len(communities),
        "output_dir": str(output_dir),
        "dicom_count": len(detection.get("files", {}).get("dicom", [])),
    }
