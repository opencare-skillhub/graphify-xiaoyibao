from __future__ import annotations

import json
import subprocess
import sys

import pytest

import xyb.__main__ as cli


def test_report_command_writes_summary(tmp_path) -> None:
    records = tmp_path / 'records'
    records.mkdir()
    (records / 'note.md').write_text('hello', encoding='utf-8')
    out_dir = tmp_path / 'out'
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'report', str(records), '--output-dir', str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (out_dir / 'MEDICAL_SUMMARY.md').exists()


def test_update_command_prints_incremental_json(tmp_path) -> None:
    records = tmp_path / 'records'
    records.mkdir()
    (records / 'note.md').write_text('hello', encoding='utf-8')
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'update', str(records)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'incremental' in result.stdout


def test_extract_command_prints_structured_json_for_directory(tmp_path) -> None:
    records = tmp_path / 'records'
    records.mkdir()
    (records / 'main.py').write_text('print(\"hi\")\n', encoding='utf-8')
    (records / 'note.md').write_text('hello', encoding='utf-8')
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'extract', str(records)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert set(payload.keys()) >= {'nodes', 'edges', 'hyperedges'}
    assert len(payload['nodes']) >= 1


def test_backfill_merge_command_writes_audit(tmp_path) -> None:
    out = tmp_path / 'graphify-out'
    out.mkdir()
    (out / '.graphify_detect.json').write_text(json.dumps({
        'total_files': 1,
        'total_words': 10,
        'medical_directory_hits': {},
    }, ensure_ascii=False), encoding='utf-8')
    (out / '.graphify_semantic.json').write_text(json.dumps({
        'nodes': [{'id': 'old', 'label': 'old', 'source_file': 'a.pdf'}],
        'edges': [],
        'hyperedges': [],
        'input_tokens': 0,
        'output_tokens': 0,
    }, ensure_ascii=False), encoding='utf-8')
    (out / '.graphify_ast.json').write_text(json.dumps({
        'nodes': [],
        'edges': [],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    (out / '.graphify_standard_chunk_1.json').write_text(json.dumps({
        'source_files': ['a.pdf'],
        'nodes': [{'id': 'new', 'label': 'new', 'source_file': 'a.pdf'}],
        'edges': [],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'backfill-merge', str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload['summary']['chunk_count'] == 1
    assert (out / 'semantic_backfill_merge_audit.json').exists()


def test_build_command_writes_graph_json(tmp_path) -> None:
    extraction_path = tmp_path / 'extract.json'
    extraction_path.write_text(json.dumps({
        'nodes': [
            {'id': 'n1', 'label': 'Node 1'},
            {'id': 'n2', 'label': 'Node 2'},
        ],
        'edges': [
            {'source': 'n1', 'target': 'n2', 'relation': 'related_to'},
        ],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    out_dir = tmp_path / 'build-out'
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'build', str(extraction_path), '--output-dir', str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload['nodes'] == 2
    assert payload['edges'] == 1
    assert (out_dir / 'graph.json').exists()


def test_graph_report_command_writes_graph_and_report(tmp_path) -> None:
    extraction_path = tmp_path / 'extract.json'
    extraction_path.write_text(json.dumps({
        'nodes': [
            {'id': 'n1', 'label': 'Node 1', 'file_type': 'code', 'source_file': 'a.py'},
            {'id': 'n2', 'label': 'Node 2', 'file_type': 'code', 'source_file': 'a.py'},
        ],
        'edges': [
            {'source': 'n1', 'target': 'n2', 'relation': 'related_to', 'confidence': 'EXTRACTED', 'source_file': 'a.py'},
        ],
        'hyperedges': [],
        'input_tokens': 0,
        'output_tokens': 0,
    }, ensure_ascii=False), encoding='utf-8')
    out_dir = tmp_path / 'report-out'
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'graph-report', str(extraction_path), '--output-dir', str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload['nodes'] == 2
    assert (out_dir / 'graph.json').exists()
    assert (out_dir / 'GRAPH_REPORT.md').exists()
    assert (out_dir / 'graph.html').exists()
    assert (out_dir / '.graphify_analysis.json').exists()
    assert (out_dir / '.graphify_labels.json').exists()


def test_query_command_prints_matching_subgraph(tmp_path) -> None:
    graph_path = tmp_path / 'graph.json'
    graph_path.write_text(json.dumps({
        'directed': False,
        'multigraph': False,
        'graph': {},
        'nodes': [
            {'id': 'n1', 'label': 'Pancreas', 'source_file': 'a.md', 'community': 0, 'norm_label': 'pancreas'},
            {'id': 'n2', 'label': 'Tumor', 'source_file': 'a.md', 'community': 0, 'norm_label': 'tumor'},
        ],
        'links': [
            {'source': 'n1', 'target': 'n2', 'relation': 'related_to', 'confidence': 'EXTRACTED'},
        ],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'query', 'pancreas', '--graph', str(graph_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'NODE Pancreas' in result.stdout
    assert 'EDGE Pancreas --related_to' in result.stdout


def test_add_command_invokes_ingest_and_prints_saved_path(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    saved = tmp_path / 'raw' / 'example.md'
    saved.parent.mkdir(parents=True)
    saved.write_text('ok', encoding='utf-8')

    def fake_ingest(url, target_dir, author=None, contributor=None):
        assert url == 'https://example.com/article'
        assert str(target_dir).endswith('raw')
        assert author == 'Alice'
        assert contributor == 'Bob'
        return saved

    monkeypatch.setattr(cli, 'ingest_url', fake_ingest, raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'add', 'https://example.com/article', '--author', 'Alice', '--contributor', 'Bob'])
    cli.main()
    out = capsys.readouterr().out
    assert 'Saved to' in out


def test_full_update_command_runs_process_and_markers(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    called = {}

    def fake_process(path, output_dir, follow_symlinks=False, ocr_backend='auto'):
        called['process'] = (str(path), str(output_dir), follow_symlinks, ocr_backend)
        return {'nodes': 1, 'edges': 0}

    def fake_markers(graph_path, output_dir, markers=None):
        called['markers'] = (str(graph_path), str(output_dir), len(markers or []))
        return {'csv': 'ok.csv'}

    monkeypatch.setattr(cli, 'process_path', fake_process, raising=False)
    monkeypatch.setattr(cli, 'generate_markers_trend', fake_markers, raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'full-update', str(tmp_path), '--output-dir', str(tmp_path / 'out')])
    cli.main()
    out = capsys.readouterr().out
    assert 'markers_trend' in out
    assert 'process' in called
    assert 'markers' in called
    assert called['process'][3] == 'auto'


def test_process_command_accepts_ocr_backend(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    called = {}

    def fake_process(path, output_dir, follow_symlinks=False, ocr_backend='auto'):
        called['process'] = (str(path), str(output_dir), follow_symlinks, ocr_backend)
        return {'nodes': 1, 'edges': 0}

    monkeypatch.setattr(cli, 'process_path', fake_process, raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'process', str(tmp_path), '--ocr-backend', 'tesseract'])
    cli.main()
    capsys.readouterr()
    assert called['process'][3] == 'tesseract'


def test_path_command_prints_shortest_path(tmp_path) -> None:
    graph_path = tmp_path / 'graph.json'
    graph_path.write_text(json.dumps({
        'directed': False,
        'multigraph': False,
        'graph': {},
        'nodes': [
            {'id': 'n1', 'label': 'Pancreas', 'source_file': 'a.md', 'community': 0, 'norm_label': 'pancreas'},
            {'id': 'n2', 'label': 'Tumor', 'source_file': 'a.md', 'community': 0, 'norm_label': 'tumor'},
        ],
        'links': [
            {'source': 'n1', 'target': 'n2', 'relation': 'related_to', 'confidence': 'EXTRACTED'},
        ],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'path', 'Pancreas', 'Tumor', '--graph', str(graph_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'Shortest path' in result.stdout
    assert 'Pancreas --related_to [EXTRACTED]--> Tumor' in result.stdout


def test_explain_command_prints_node_details(tmp_path) -> None:
    graph_path = tmp_path / 'graph.json'
    graph_path.write_text(json.dumps({
        'directed': False,
        'multigraph': False,
        'graph': {},
        'nodes': [
            {'id': 'n1', 'label': 'Pancreas', 'source_file': 'a.md', 'community': 0, 'norm_label': 'pancreas', 'file_type': 'document'},
            {'id': 'n2', 'label': 'Tumor', 'source_file': 'a.md', 'community': 0, 'norm_label': 'tumor', 'file_type': 'document'},
        ],
        'links': [
            {'source': 'n1', 'target': 'n2', 'relation': 'related_to', 'confidence': 'EXTRACTED'},
        ],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'explain', 'Pancreas', '--graph', str(graph_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'Node: Pancreas' in result.stdout
    assert 'Connections (1):' in result.stdout


def test_analyze_command_writes_extract_graph_and_report(tmp_path) -> None:
    records = tmp_path / 'records'
    records.mkdir()
    (records / 'main.py').write_text(
        'def helper():\n'
        '    return 1\n\n'
        'def main():\n'
        '    return helper()\n',
        encoding='utf-8',
    )
    out_dir = tmp_path / 'analyze-out'
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'analyze', str(records), '--output-dir', str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload['nodes'] >= 1
    assert (out_dir / '.graphify_extract.json').exists()
    assert (out_dir / 'graph.json').exists()
    assert (out_dir / 'GRAPH_REPORT.md').exists()


def test_serve_command_invokes_serve_graph(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    called = {}

    def fake_serve(graph_path):
        called['graph'] = graph_path
        print(f'serving {graph_path}')

    monkeypatch.setattr(cli, 'serve_graph', fake_serve, raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'serve', 'graphify-out/graph.json'])
    cli.main()
    out = capsys.readouterr().out
    assert called['graph'] == 'graphify-out/graph.json'
    assert 'serving graphify-out/graph.json' in out


def test_install_command_invokes_install_local(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, 'install_local', lambda path: 'installed local agents', raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'install'])
    cli.main()
    assert 'installed local agents' in capsys.readouterr().out


def test_install_command_invokes_global_install(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, 'install_global_platform', lambda platform: f'global {platform} installed', raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'install', '--global-platform', 'codex'])
    cli.main()
    assert 'global codex installed' in capsys.readouterr().out


def test_hook_command_invokes_status(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, 'hook_status', lambda path: 'post-commit: installed', raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'hook', 'status'])
    cli.main()
    assert 'post-commit: installed' in capsys.readouterr().out


def test_claude_install_command_invokes_install(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, 'install_claude_local', lambda path: 'claude installed', raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'claude', 'install'])
    cli.main()
    assert 'claude installed' in capsys.readouterr().out


def test_claude_install_with_hook_invokes_hook_install(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, 'install_claude_local', lambda path: 'claude installed', raising=False)
    monkeypatch.setattr(cli, 'hook_install', lambda path: 'hook installed', raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'claude', 'install', '--hook'])
    cli.main()
    out = capsys.readouterr().out
    assert 'claude installed' in out
    assert 'hook installed' in out


def test_codex_install_command_invokes_install(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, 'install_codex_local', lambda path: 'codex installed', raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'codex', 'install'])
    cli.main()
    assert 'codex installed' in capsys.readouterr().out


def test_opencode_install_command_invokes_install(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, 'install_opencode_local', lambda path: 'opencode installed', raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'opencode', 'install'])
    cli.main()
    assert 'opencode installed' in capsys.readouterr().out


def test_cursor_install_command_invokes_install(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, 'install_cursor_local', lambda path: 'cursor installed', raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'cursor', 'install'])
    cli.main()
    assert 'cursor installed' in capsys.readouterr().out


def test_gemini_install_command_invokes_install(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, 'install_gemini_local', lambda path: 'gemini installed', raising=False)
    monkeypatch.setattr(sys, 'argv', ['xyb', 'gemini', 'install'])
    cli.main()
    assert 'gemini installed' in capsys.readouterr().out


def test_wiki_command_writes_index(tmp_path) -> None:
    graph_path = tmp_path / 'graph.json'
    graph_path.write_text(json.dumps({
        'directed': False,
        'multigraph': False,
        'graph': {},
        'nodes': [
            {'id': 'n1', 'label': 'Pancreas', 'source_file': 'a.md', 'community': 0, 'norm_label': 'pancreas', 'file_type': 'document'},
            {'id': 'n2', 'label': 'Tumor', 'source_file': 'a.md', 'community': 0, 'norm_label': 'tumor', 'file_type': 'document'},
        ],
        'links': [
            {'source': 'n1', 'target': 'n2', 'relation': 'related_to', 'confidence': 'EXTRACTED'},
        ],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    out_dir = tmp_path / 'wiki'
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'wiki', str(graph_path), '--output-dir', str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload['articles'] >= 1
    assert (out_dir / 'index.md').exists()


def test_graphml_command_writes_graphml(tmp_path) -> None:
    graph_path = tmp_path / 'graph.json'
    graph_path.write_text(json.dumps({
        'directed': False,
        'multigraph': False,
        'graph': {},
        'nodes': [
            {'id': 'n1', 'label': 'Pancreas', 'source_file': 'a.md', 'community': 0, 'norm_label': 'pancreas', 'file_type': 'document'},
            {'id': 'n2', 'label': 'Tumor', 'source_file': 'b.md', 'community': 1, 'norm_label': 'tumor', 'file_type': 'document'},
        ],
        'links': [
            {'source': 'n1', 'target': 'n2', 'relation': 'related_to', 'confidence': 'EXTRACTED'},
        ],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    out_path = tmp_path / 'graph.graphml'
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'graphml', str(graph_path), '--output', str(out_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload['output'] == str(out_path)
    assert out_path.exists()


def test_obsidian_command_writes_vault(tmp_path) -> None:
    graph_path = tmp_path / 'graph.json'
    graph_path.write_text(json.dumps({
        'directed': False,
        'multigraph': False,
        'graph': {},
        'nodes': [
            {'id': 'n1', 'label': 'Pancreas', 'source_file': 'a.md', 'community': 0, 'norm_label': 'pancreas', 'file_type': 'document'},
            {'id': 'n2', 'label': 'Tumor', 'source_file': 'b.md', 'community': 0, 'norm_label': 'tumor', 'file_type': 'document'},
        ],
        'links': [
            {'source': 'n1', 'target': 'n2', 'relation': 'related_to', 'confidence': 'EXTRACTED'},
        ],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    out_dir = tmp_path / 'obsidian'
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'obsidian', str(graph_path), '--output-dir', str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload['output_dir'] == str(out_dir)
    assert payload['notes'] >= 2
    assert (out_dir / '.obsidian' / 'graph.json').exists()


def test_neo4j_command_writes_cypher(tmp_path) -> None:
    graph_path = tmp_path / 'graph.json'
    graph_path.write_text(json.dumps({
        'directed': False,
        'multigraph': False,
        'graph': {},
        'nodes': [
            {'id': 'n1', 'label': 'Pancreas', 'source_file': 'a.md', 'community': 0, 'norm_label': 'pancreas', 'file_type': 'document'},
            {'id': 'n2', 'label': 'Tumor', 'source_file': 'b.md', 'community': 0, 'norm_label': 'tumor', 'file_type': 'document'},
        ],
        'links': [
            {'source': 'n1', 'target': 'n2', 'relation': 'related_to', 'confidence': 'EXTRACTED'},
        ],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    out_path = tmp_path / 'neo4j.cypher'
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'neo4j', str(graph_path), '--output', str(out_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload['output'] == str(out_path)
    assert out_path.exists()
    assert 'MERGE' in out_path.read_text(encoding='utf-8')


def test_neo4j_push_command_invokes_driver(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    graph_path = tmp_path / 'graph.json'
    graph_path.write_text(json.dumps({
        'directed': False,
        'multigraph': False,
        'graph': {},
        'nodes': [
            {'id': 'n1', 'label': 'Pancreas', 'source_file': 'a.md', 'community': 0, 'norm_label': 'pancreas', 'file_type': 'document'},
            {'id': 'n2', 'label': 'Tumor', 'source_file': 'b.md', 'community': 0, 'norm_label': 'tumor', 'file_type': 'document'},
        ],
        'links': [
            {'source': 'n1', 'target': 'n2', 'relation': 'related_to', 'confidence': 'EXTRACTED'},
        ],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')

    def fake_push(graph, uri, user, password, communities=None):
        assert graph.number_of_nodes() == 2
        assert uri == 'bolt://localhost:7687'
        assert user == 'neo4j'
        assert password == 'secret'
        assert communities == {0: ['n1', 'n2']}
        return {'nodes': 2, 'edges': 1}

    monkeypatch.setattr(cli, 'push_to_neo4j', fake_push, raising=False)
    monkeypatch.setattr(sys, 'argv', [
        'xyb', 'neo4j-push', str(graph_path),
        '--uri', 'bolt://localhost:7687',
        '--user', 'neo4j',
        '--password', 'secret',
    ])
    cli.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload['nodes'] == 2
    assert payload['edges'] == 1


def test_explain_command_prints_medical_bucket_details(tmp_path) -> None:
    graph_path = tmp_path / 'graph.json'
    graph_path.write_text(json.dumps({
        'directed': False,
        'multigraph': False,
        'graph': {},
        'nodes': [
            {'id': 'n1', 'label': 'CA19-9', 'source_file': 'records/06_检验指标与曲线/labs.md', 'community': 1, 'norm_label': 'ca19-9', 'file_type': 'document'},
            {'id': 'n2', 'label': 'Trend', 'source_file': 'records/06_检验指标与曲线/labs.md', 'community': 1, 'norm_label': 'trend', 'file_type': 'document'},
        ],
        'links': [
            {'source': 'n1', 'target': 'n2', 'relation': 'tracked_with', 'confidence': 'EXTRACTED', 'source_file': 'records/06_检验指标与曲线/labs.md'},
        ],
        'hyperedges': [],
    }, ensure_ascii=False), encoding='utf-8')
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'explain', 'CA19-9', '--graph', str(graph_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'Medical Bucket: labs_markers' in result.stdout


def test_analyze_command_includes_medical_layout_signals(tmp_path) -> None:
    records = tmp_path / 'records'
    (records / '02_确诊信息').mkdir(parents=True)
    (records / '04_治疗记录').mkdir(parents=True)
    (records / '02_确诊信息' / 'note.md').write_text('diagnosis confirmed', encoding='utf-8')
    (records / '04_治疗记录' / 'plan.md').write_text('treatment plan', encoding='utf-8')
    out_dir = tmp_path / 'analyze-out'
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'analyze', str(records), '--output-dir', str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    report_text = (out_dir / 'GRAPH_REPORT.md').read_text(encoding='utf-8')
    assert '## Medical Record Layout Signals' in report_text
    assert '- diagnosis: 1' in report_text
    assert '- treatment: 1' in report_text
