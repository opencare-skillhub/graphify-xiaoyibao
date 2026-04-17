from __future__ import annotations

from xyb_core.semantic.merge import merge_semantic_chunks
from xyb_core.update import run_semantic_backfill


def test_merge_semantic_chunks_replaces_by_source_file() -> None:
    existing = {
        "nodes": [{"id": "old-a", "source_file": "a.pdf"}],
        "edges": [],
        "hyperedges": [],
        "input_tokens": 1,
        "output_tokens": 1,
    }
    incoming = [{
        "nodes": [{"id": "new-a", "source_file": "a.pdf"}],
        "edges": [],
        "hyperedges": [],
    }]
    merged, audit = merge_semantic_chunks(existing=existing, incoming=incoming, detected_files=["a.pdf", "b.png"])
    assert [node["id"] for node in merged["nodes"]] == ["new-a"]
    assert audit["replaced_files"] == ["a.pdf"]
    assert audit["unresolved_files"] == ["b.png"]


def test_run_semantic_backfill_returns_semantic_and_audit() -> None:
    result = run_semantic_backfill(
        detected_files=["a.pdf"],
        existing_semantic={"nodes": [], "edges": [], "hyperedges": []},
        chunk_results=[{"nodes": [{"id": "new-a", "source_file": "a.pdf"}], "edges": [], "hyperedges": []}],
    )
    assert result["semantic"]["nodes"][0]["id"] == "new-a"
    assert result["audit"]["replaced_files"] == ["a.pdf"]
