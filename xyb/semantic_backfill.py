from __future__ import annotations

import glob
import json
from copy import deepcopy
from pathlib import Path

from xyb.analyze import god_nodes, surprising_connections, suggest_questions
from xyb.build import build_from_json
from xyb.cluster import cluster, score_all
from xyb.export import to_html, to_json
from xyb.report import generate

VALID_FILE_TYPES = {"code", "document", "image", "paper", "rationale"}
EXT_MAP = {
    "md": "document", "txt": "document", "json": "document", "html": "document", "htm": "document",
    "docx": "document", "pdf": "paper", "py": "code", "js": "code", "ts": "code", "tsx": "code",
    "jsx": "code", "jpg": "image", "jpeg": "image", "png": "image", "gif": "image", "webp": "image",
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_file_type(node: dict) -> str:
    ft = node.get("file_type")
    typ = node.get("type")
    if ft in VALID_FILE_TYPES:
        return ft
    if isinstance(ft, str):
        key = ft.lower().lstrip(".")
        if key in EXT_MAP:
            return EXT_MAP[key]
    if isinstance(typ, str):
        key = typ.lower()
        if key in {"script", "code", "module", "function", "class"}:
            return "code"
        if key in {"image", "scan", "screenshot"}:
            return "image"
    sf = node.get("source_file")
    if isinstance(sf, str):
        ext = Path(sf).suffix.lower().lstrip(".")
        if ext in EXT_MAP:
            return EXT_MAP[ext]
    return "document"


def _normalize_node(node: dict) -> dict:
    node = deepcopy(node)
    sf = node.get("source_file")
    if isinstance(sf, list):
        node["source_file"] = sf[0] if sf else None
        node.setdefault("attributes", {})
        if isinstance(node["attributes"], dict):
            node["attributes"]["source_file_aliases"] = sf[1:]
    node["file_type"] = _norm_file_type(node)
    return node


def _normalize_edge(edge: dict) -> dict:
    edge = deepcopy(edge)
    sf = edge.get("source_file")
    if isinstance(sf, list):
        edge["source_file"] = sf[0] if sf else None
    return edge


def merge_semantic_chunks(*, existing: dict, incoming: list[dict], detected_files: list[str]) -> tuple[dict, dict]:
    replace_files = {
        node["source_file"]
        for chunk in incoming
        for node in chunk.get("nodes", [])
        if isinstance(node.get("source_file"), str)
    }
    kept_nodes = [node for node in existing.get("nodes", []) if node.get("source_file") not in replace_files]
    new_nodes = [_normalize_node(node) for chunk in incoming for node in chunk.get("nodes", [])]
    kept_edges = [edge for edge in existing.get("edges", []) if edge.get("source_file") not in replace_files]
    new_edges = [_normalize_edge(edge) for chunk in incoming for edge in chunk.get("edges", [])]
    new_hyperedges = [hyper for chunk in incoming for hyper in chunk.get("hyperedges", [])]
    merged = {
        "nodes": kept_nodes + new_nodes,
        "edges": kept_edges + new_edges,
        "hyperedges": existing.get("hyperedges", []) + new_hyperedges,
        "input_tokens": existing.get("input_tokens", 0),
        "output_tokens": existing.get("output_tokens", 0),
    }
    unresolved = sorted(set(detected_files) - replace_files)
    audit = {
        "replaced_files": sorted(replace_files),
        "unresolved_files": unresolved,
    }
    return merged, audit


def _rebuild_outputs(out: Path, detect_info: dict, extraction: dict) -> dict:
    G = build_from_json(extraction)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    labels = {}
    for cid, nids in communities.items():
        names = []
        for nid in nids[:3]:
            label = G.nodes[nid].get("label", nid)
            if label not in names:
                names.append(label)
        labels[cid] = " / ".join(names[:3]) if names else f"Community {cid}"
    questions = suggest_questions(G, communities, labels)
    analysis = {
        "communities": {str(k): v for k, v in communities.items()},
        "cohesion": {str(k): v for k, v in cohesion.items()},
        "gods": gods,
        "surprises": surprises,
        "questions": questions,
    }
    (out / ".graphify_analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / ".graphify_labels.json").write_text(json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    report = generate(G, communities, cohesion, labels, gods, surprises, detect_info, {"input": extraction.get("input_tokens", 0), "output": extraction.get("output_tokens", 0)}, ".", suggested_questions=questions)
    (out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    to_json(G, communities, str(out / "graph.json"))
    if G.number_of_nodes() <= 5000:
        to_html(G, communities, str(out / "graph.html"), community_labels=labels)
    return {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "communities": len(communities)}


def merge_backfill_files(graphify_out: Path, chunks_glob: str | None = None, chunk_plan: str | None = None) -> dict:
    out = Path(graphify_out)
    detect_info = _load(out / ".graphify_detect.json")
    semantic = _load(out / ".graphify_semantic.json")
    ast = _load(out / ".graphify_ast.json") if (out / ".graphify_ast.json").exists() else {"nodes": [], "edges": [], "hyperedges": []}
    chunk_plan_path = Path(chunk_plan) if chunk_plan else (out / ".graphify_standard_chunks.json")
    plan = {int(x["chunk"]): x["files"] for x in _load(chunk_plan_path)} if chunk_plan_path.exists() else {}

    chunk_pattern = chunks_glob or str(out / ".graphify_standard_chunk_*.json")
    chunk_paths = sorted(glob.glob(chunk_pattern))
    chunk_audit = []
    incoming = []
    detected_files = []

    for path_str in chunk_paths:
        path = Path(path_str)
        raw = _load(path)
        incoming.append(raw)
        chunk_num = int(path.stem.split("_")[-1])
        declared = list(raw.get("source_files") or [])
        if not declared:
            vals = []
            for item in raw.get("nodes", []) + raw.get("edges", []):
                sf = item.get("source_file")
                if isinstance(sf, str):
                    vals.append(sf)
            declared = sorted(set(vals))
        detected_files.extend(declared)
        chunk_audit.append({
            "chunk": chunk_num,
            "planned_files": plan.get(chunk_num, []),
            "declared_source_files": declared,
            "replace_mode": bool(declared),
            "nodes": len(raw.get("nodes", [])),
            "edges": len(raw.get("edges", [])),
        })

    merged_semantic, merge_audit = merge_semantic_chunks(existing=semantic, incoming=incoming, detected_files=sorted(set(detected_files)))
    (out / ".graphify_semantic.json").write_text(json.dumps(merged_semantic, ensure_ascii=False, indent=2), encoding="utf-8")

    seen = {n["id"] for n in ast.get("nodes", []) if isinstance(n.get("id"), str)}
    extract_nodes = list(ast.get("nodes", []))
    for node in merged_semantic["nodes"]:
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id not in seen:
            seen.add(node_id)
            extract_nodes.append(node)

    merged_extract = {
        "nodes": extract_nodes,
        "edges": ast.get("edges", []) + merged_semantic["edges"],
        "hyperedges": merged_semantic.get("hyperedges", []),
        "input_tokens": merged_semantic.get("input_tokens", 0),
        "output_tokens": merged_semantic.get("output_tokens", 0),
    }
    (out / ".graphify_extract.json").write_text(json.dumps(merged_extract, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = _rebuild_outputs(out, detect_info, merged_extract)
    audit = {
        "summary": {
            "chunk_count": len(chunk_paths),
            "replace_files": len(merge_audit["replaced_files"]),
            **stats,
        },
        "merge": merge_audit,
        "chunks": chunk_audit,
    }
    (out / "semantic_backfill_merge_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit
