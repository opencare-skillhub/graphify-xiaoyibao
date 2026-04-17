from __future__ import annotations

from xyb_core.semantic.merge import merge_semantic_chunks


def run_semantic_backfill(*, detected_files: list[str], existing_semantic: dict, chunk_results: list[dict]) -> dict:
    merged, audit = merge_semantic_chunks(
        existing=existing_semantic,
        incoming=chunk_results,
        detected_files=detected_files,
    )
    return {"semantic": merged, "audit": audit}
