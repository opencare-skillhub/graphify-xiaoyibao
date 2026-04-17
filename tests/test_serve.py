from __future__ import annotations

import json

from xyb.serve import _load_graph


def test_load_graph_reads_json_graph(tmp_path) -> None:
    path = tmp_path / 'graph.json'
    path.write_text(json.dumps({'nodes': [], 'links': []}), encoding='utf-8')
    graph = _load_graph(str(path))
    assert graph.number_of_nodes() == 0
