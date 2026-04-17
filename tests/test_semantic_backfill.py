from __future__ import annotations

from xyb.semantic_backfill import merge_semantic_chunks


def test_merge_semantic_chunks_replaces_matching_source_file() -> None:
    merged, audit = merge_semantic_chunks(
        existing={'nodes': [{'id': 'old', 'source_file': 'a.pdf'}], 'edges': [], 'hyperedges': []},
        incoming=[{'nodes': [{'id': 'new', 'source_file': 'a.pdf'}], 'edges': [], 'hyperedges': []}],
        detected_files=['a.pdf', 'b.png'],
    )
    assert [n['id'] for n in merged['nodes']] == ['new']
    assert audit['replaced_files'] == ['a.pdf']
