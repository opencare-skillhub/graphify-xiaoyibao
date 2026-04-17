from __future__ import annotations


def merge_semantic_chunks(*, existing: dict, incoming: list[dict], detected_files: list[str]) -> tuple[dict, dict]:
    replace_files = {
        node["source_file"]
        for chunk in incoming
        for node in chunk.get("nodes", [])
        if isinstance(node.get("source_file"), str)
    }

    kept_nodes = [
        node for node in existing.get("nodes", [])
        if node.get("source_file") not in replace_files
    ]
    new_nodes = [node for chunk in incoming for node in chunk.get("nodes", [])]

    kept_edges = [
        edge for edge in existing.get("edges", [])
        if edge.get("source_file") not in replace_files
    ]
    new_edges = [edge for chunk in incoming for edge in chunk.get("edges", [])]
    new_hyperedges = [hyper for chunk in incoming for hyper in chunk.get("hyperedges", [])]

    merged = {
        "nodes": kept_nodes + new_nodes,
        "edges": kept_edges + new_edges,
        "hyperedges": existing.get("hyperedges", []) + new_hyperedges,
        "input_tokens": existing.get("input_tokens", 0),
        "output_tokens": existing.get("output_tokens", 0),
    }

    detected_set = set(detected_files)
    unresolved = sorted(detected_set - replace_files)
    audit = {
        "replaced_files": sorted(replace_files),
        "unresolved_files": unresolved,
    }
    return merged, audit
