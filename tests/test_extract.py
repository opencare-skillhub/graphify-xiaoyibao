from __future__ import annotations

from pathlib import Path

from xyb.extract import extract


def test_extract_returns_structured_payload_for_empty_files() -> None:
    result = extract([])
    assert set(result.keys()) >= {'nodes', 'edges', 'hyperedges'}
    assert result['nodes'] == []


def test_extract_python_file_emits_function_nodes_and_call_edge(tmp_path: Path) -> None:
    sample = tmp_path / 'sample.py'
    sample.write_text(
        'import os\n\n'
        'def helper():\n'
        '    return 1\n\n'
        'def main():\n'
        '    helper()\n',
        encoding='utf-8',
    )
    result = extract([sample])
    labels = {node['label'] for node in result['nodes']}
    relations = {(edge['relation'], edge['source'], edge['target']) for edge in result['edges']}
    assert 'helper()' in labels
    assert 'main()' in labels
    assert any(rel == 'calls' for rel, _, _ in relations)
