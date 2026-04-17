from __future__ import annotations

from xyb.build import build_from_json


def test_build_from_minimal_json() -> None:
    graph = build_from_json({'nodes': [], 'edges': [], 'hyperedges': []})
    assert graph.number_of_nodes() == 0
    assert graph.number_of_edges() == 0
