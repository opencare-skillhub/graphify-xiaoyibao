from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import networkx as nx

from xyb.analyze import god_nodes, surprising_connections, suggest_questions
from xyb.build import build_from_json
from xyb.cluster import cluster, score_all
from xyb.detect import detect, detect_incremental, medical_bucket_for_path, summarize_medical_layout
from xyb.extract import collect_files, extract
from xyb.export import push_to_neo4j, to_cypher, to_graphml, to_html, to_json, to_obsidian
from xyb.init import init_patient_records
from xyb.ingest import ingest as ingest_url
from xyb.install import (
    install_cursor_local,
    install_claude_local,
    install_codex_local,
    install_gemini_local,
    install_global_platform,
    install_local,
    install_opencode_local,
    uninstall_global_platform,
    uninstall_cursor_local,
    uninstall_claude_local,
    uninstall_codex_local,
    uninstall_gemini_local,
    uninstall_local,
    uninstall_opencode_local,
)
from xyb.hooks import install as hook_install, status as hook_status, uninstall as hook_uninstall
from xyb.report import generate, write_medical_summary_report
from xyb.process import process_path
from xyb.markers_trend import MARKERS, generate_markers_trend
from xyb.ocr import OCR_BACKENDS
from xyb.serve import _bfs, _dfs, _load_graph, _score_nodes, _subgraph_to_text, serve as serve_graph
from xyb.semantic_backfill import merge_backfill_files
from xyb.wiki import to_wiki
from xyb.watch import watch as watch_folder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='xyb', description='xiaoyibao CLI')
    parser.add_argument('--version', action='store_true', help='show xyb version and exit')

    subparsers = parser.add_subparsers(dest='command')

    init_parser = subparsers.add_parser('init', help='create patient records template in target directory')
    init_parser.add_argument('path', help='target directory for patient records template')
    init_parser.add_argument('--force', action='store_true', help='overwrite existing template content in target directory')

    install_parser = subparsers.add_parser('install', help='install minimal local xyb instructions into AGENTS.md')
    install_parser.add_argument('action', nargs='?', default='install', choices=['install', 'uninstall'], help='install or uninstall local project instructions')
    install_parser.add_argument('--global-platform', choices=['claude', 'codex', 'opencode', 'cursor', 'gemini'], default=None, help='install/uninstall global platform skeleton config')

    claude_parser = subparsers.add_parser('claude', help='manage minimal local Claude project instructions')
    claude_parser.add_argument('action', choices=['install', 'uninstall'], help='claude action')
    claude_parser.add_argument('--hook', action='store_true', help='also run `xyb hook install` in current git repo')

    codex_parser = subparsers.add_parser('codex', help='manage minimal local Codex project instructions')
    codex_parser.add_argument('action', choices=['install', 'uninstall'], help='codex action')
    codex_parser.add_argument('--hook', action='store_true', help='also run `xyb hook install` in current git repo')

    opencode_parser = subparsers.add_parser('opencode', help='manage minimal local Opencode project instructions')
    opencode_parser.add_argument('action', choices=['install', 'uninstall'], help='opencode action')
    opencode_parser.add_argument('--hook', action='store_true', help='also run `xyb hook install` in current git repo')

    cursor_parser = subparsers.add_parser('cursor', help='manage minimal local Cursor project instructions')
    cursor_parser.add_argument('action', choices=['install', 'uninstall'], help='cursor action')
    cursor_parser.add_argument('--hook', action='store_true', help='also run `xyb hook install` in current git repo')

    gemini_parser = subparsers.add_parser('gemini', help='manage minimal local Gemini project instructions')
    gemini_parser.add_argument('action', choices=['install', 'uninstall'], help='gemini action')
    gemini_parser.add_argument('--hook', action='store_true', help='also run `xyb hook install` in current git repo')

    scan_parser = subparsers.add_parser('scan', help='scan a directory recursively and print detect summary as json')
    scan_parser.add_argument('path', help='directory to scan')
    scan_parser.add_argument('--follow-symlinks', action='store_true', help='follow symlinks while scanning')

    process_parser = subparsers.add_parser('process', help='medical-first processing pipeline (non-code + DICOM metadata)')
    process_parser.add_argument('path', help='directory to process')
    process_parser.add_argument('--follow-symlinks', action='store_true', help='follow symlinks while scanning')
    process_parser.add_argument('--output-dir', default=None, help='directory to write graph/report artifacts (default: <project-root>/xiaoyibao-out)')
    process_parser.add_argument('--ocr-backend', choices=OCR_BACKENDS, default='auto', help='backend selection: auto|host-cli|multimodal|paddle-local|paddle-api|mineru-local|mineru-api|tesseract')
    process_parser.add_argument('--retry-failed-only', action='store_true', help='only retry files listed in xiaoyibao-out/ocr_failures_mineru.jsonl')

    full_parser = subparsers.add_parser('full-update', help='run process then markers-trend in one command')
    full_parser.add_argument('path', help='directory to process')
    full_parser.add_argument('--follow-symlinks', action='store_true', help='follow symlinks while scanning')
    full_parser.add_argument('--output-dir', default=None, help='directory to write graph/report/trend artifacts (default: <project-root>/xiaoyibao-out)')
    full_parser.add_argument('--ocr-backend', choices=OCR_BACKENDS, default='auto', help='backend selection: auto|host-cli|multimodal|paddle-local|paddle-api|mineru-local|mineru-api|tesseract')
    full_parser.add_argument('--retry-failed-only', action='store_true', help='only retry files listed in xiaoyibao-out/ocr_failures_mineru.jsonl')
    full_parser.add_argument(
        '--markers',
        default=",".join(m.key for m in MARKERS),
        help='comma-separated marker keys, e.g. ca19_9,cea,afp,ca50,ca72_4,ca125',
    )

    marker_parser = subparsers.add_parser('markers-trend', help='build tumor marker trend csv/png/summary from graph.json')
    marker_parser.add_argument('--graph', default='xiaoyibao-out/graph.json', help='graph json path')
    marker_parser.add_argument('--output-dir', default='xiaoyibao-out', help='output directory for trend artifacts')
    marker_parser.add_argument(
        '--markers',
        default=",".join(m.key for m in MARKERS),
        help='comma-separated marker keys, e.g. ca19_9,cea,afp,ca50,ca72_4,ca125',
    )

    extract_parser = subparsers.add_parser('extract', help='extract graph payload from files collected under a path')
    extract_parser.add_argument('path', help='file or directory to extract')
    extract_parser.add_argument('--follow-symlinks', action='store_true', help='follow symlinks while collecting files')

    analyze_parser = subparsers.add_parser('analyze', help='run extract + graph-report on a directory in one command')
    analyze_parser.add_argument('path', help='directory to analyze')
    analyze_parser.add_argument('--follow-symlinks', action='store_true', help='follow symlinks while collecting files')
    analyze_parser.add_argument('--output-dir', default='graphify-out', help='directory to write extraction and graph artifacts')

    build_parser = subparsers.add_parser('build', help='build graph artifacts from an extraction json file')
    build_parser.add_argument('path', help='extraction json path')
    build_parser.add_argument('--output-dir', default='graphify-out', help='directory to write graph.json')

    graph_report_parser = subparsers.add_parser('graph-report', help='build graph artifacts and write GRAPH_REPORT.md from an extraction json file')
    graph_report_parser.add_argument('path', help='extraction json path')
    graph_report_parser.add_argument('--output-dir', default='graphify-out', help='directory to write graph.json and GRAPH_REPORT.md')

    add_parser = subparsers.add_parser('add', help='fetch a url into a local records/raw directory')
    add_parser.add_argument('url', help='url to fetch')
    add_parser.add_argument('--author', default=None, help='original author')
    add_parser.add_argument('--contributor', default=None, help='who added this item')
    add_parser.add_argument('--dir', default='raw', help='target directory for fetched content')

    query_parser = subparsers.add_parser('query', help='query a graph.json and print a focused subgraph as text')
    query_parser.add_argument('question', help='natural language query or keywords')
    query_parser.add_argument('--dfs', action='store_true', help='use DFS instead of BFS')
    query_parser.add_argument('--budget', type=int, default=2000, help='approximate token budget for output')
    query_parser.add_argument('--graph', default='graphify-out/graph.json', help='graph json path')

    path_parser = subparsers.add_parser('path', help='print the shortest path between two graph concepts')
    path_parser.add_argument('source', help='source concept label or keyword')
    path_parser.add_argument('target', help='target concept label or keyword')
    path_parser.add_argument('--graph', default='graphify-out/graph.json', help='graph json path')

    explain_parser = subparsers.add_parser('explain', help='print details for a single graph node')
    explain_parser.add_argument('label', help='node label or keyword')
    explain_parser.add_argument('--graph', default='graphify-out/graph.json', help='graph json path')

    serve_parser = subparsers.add_parser('serve', help='start MCP stdio server for a graph.json')
    serve_parser.add_argument('graph', nargs='?', default='graphify-out/graph.json', help='graph json path')

    wiki_parser = subparsers.add_parser('wiki', help='export an agent-crawlable wiki from graph.json')
    wiki_parser.add_argument('graph', help='graph json path')
    wiki_parser.add_argument('--output-dir', default='graphify-out/wiki', help='wiki output directory')

    graphml_parser = subparsers.add_parser('graphml', help='export graph.json to GraphML')
    graphml_parser.add_argument('graph', help='graph json path')
    graphml_parser.add_argument('--output', default='graphify-out/graph.graphml', help='graphml output path')

    obsidian_parser = subparsers.add_parser('obsidian', help='export graph.json to an Obsidian vault')
    obsidian_parser.add_argument('graph', help='graph json path')
    obsidian_parser.add_argument('--output-dir', default='graphify-out/obsidian', help='obsidian vault output directory')

    neo4j_parser = subparsers.add_parser('neo4j', help='export graph.json to Neo4j Cypher import script')
    neo4j_parser.add_argument('graph', help='graph json path')
    neo4j_parser.add_argument('--output', default='graphify-out/neo4j.cypher', help='cypher output path')

    neo4j_push_parser = subparsers.add_parser('neo4j-push', help='push graph.json directly to a Neo4j instance')
    neo4j_push_parser.add_argument('graph', help='graph json path')
    neo4j_push_parser.add_argument('--uri', required=True, help='Neo4j URI, e.g. bolt://localhost:7687')
    neo4j_push_parser.add_argument('--user', required=True, help='Neo4j username')
    neo4j_push_parser.add_argument('--password', required=True, help='Neo4j password')

    report_parser = subparsers.add_parser('report', help='write a medical summary report from a records directory')
    report_parser.add_argument('path', help='directory to summarize')
    report_parser.add_argument('--output-dir', default='graphify-out', help='directory to write MEDICAL_SUMMARY.md')

    update_parser = subparsers.add_parser('update', help='run incremental detect and print summary as json')
    update_parser.add_argument('path', help='directory to update')
    update_parser.add_argument('--manifest-path', default='xiaoyibao-out/manifest.json', help='manifest path for incremental diff')

    backfill_parser = subparsers.add_parser('backfill-merge', help='merge semantic backfill chunk files and rebuild graph outputs')
    backfill_parser.add_argument('path', help='graphify-out style directory containing semantic chunk files')
    backfill_parser.add_argument('--chunks-glob', default=None, help='optional glob for semantic chunk files')
    backfill_parser.add_argument('--chunk-plan', default=None, help='optional chunk plan json path')

    watch_parser = subparsers.add_parser('watch', help='watch a folder and rebuild/notify on changes')
    watch_parser.add_argument('path', nargs='?', default='.', help='folder to watch')
    watch_parser.add_argument('--debounce', type=float, default=3.0, help='seconds to wait after last change before triggering')

    hook_parser = subparsers.add_parser('hook', help='manage git hooks for automatic graph rebuilds')
    hook_parser.add_argument('action', choices=['install', 'uninstall', 'status'], help='hook action')

    return parser


def _detection_result_from_extraction(extraction: dict, fallback_root: str | Path | None = None) -> dict:
    source_files = sorted({n.get('source_file', '') for n in extraction.get('nodes', []) if n.get('source_file')})
    medical_hits = summarize_medical_layout(source_files)
    result = {
        'total_files': len(source_files),
        'total_words': 0,
        'warning': None,
        'medical_directory_hits': medical_hits,
    }
    if fallback_root is not None:
        root = Path(fallback_root)
        if root.exists() and root.is_dir():
            scanned = detect(root)
            result['total_files'] = scanned.get('total_files', result['total_files'])
            result['total_words'] = scanned.get('total_words', 0)
            result['warning'] = scanned.get('warning')
            result['medical_directory_hits'] = scanned.get('medical_directory_hits', medical_hits)
    return result


def _default_output_dir_for(path_arg: str | Path) -> Path:
    p = Path(path_arg).resolve()
    # 在 raw 目录执行时，默认把产物写到项目根目录下，避免写到 raw/xiaoyibao-out
    root = p.parent if p.name.lower() == "raw" else p
    return root / "xiaoyibao-out"


def _medical_bucket_line(source_file: str) -> str:
    bucket = medical_bucket_for_path(source_file)
    return bucket or ''


def _communities_from_graph(graph: nx.Graph) -> dict[int, list[str]]:
    communities: dict[int, list[str]] = {}
    for node_id, data in graph.nodes(data=True):
        cid = data.get('community')
        if cid is None:
            continue
        communities.setdefault(int(cid), []).append(node_id)
    return communities


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        print('xyb 0.1.1')
        return

    if args.command == 'init':
        target = init_patient_records(args.path, force=args.force)
        print(f'Initialized patient records template at {target}')
        return

    if args.command == 'install':
        if args.global_platform:
            if args.action == 'install':
                print(install_global_platform(args.global_platform))
            else:
                print(uninstall_global_platform(args.global_platform))
        elif args.action == 'install':
            print(install_local(Path('.')))
        else:
            print(uninstall_local(Path('.')))
        return

    if args.command == 'claude':
        if args.action == 'install':
            print(install_claude_local(Path('.')))
            if args.hook:
                print(hook_install(Path('.')))
        else:
            print(uninstall_claude_local(Path('.')))
        return

    if args.command == 'codex':
        if args.action == 'install':
            print(install_codex_local(Path('.')))
            if args.hook:
                print(hook_install(Path('.')))
        else:
            print(uninstall_codex_local(Path('.')))
        return

    if args.command == 'opencode':
        if args.action == 'install':
            print(install_opencode_local(Path('.')))
            if args.hook:
                print(hook_install(Path('.')))
        else:
            print(uninstall_opencode_local(Path('.')))
        return

    if args.command == 'cursor':
        if args.action == 'install':
            print(install_cursor_local(Path('.')))
            if args.hook:
                print(hook_install(Path('.')))
        else:
            print(uninstall_cursor_local(Path('.')))
        return

    if args.command == 'gemini':
        if args.action == 'install':
            print(install_gemini_local(Path('.')))
            if args.hook:
                print(hook_install(Path('.')))
        else:
            print(uninstall_gemini_local(Path('.')))
        return

    if args.command == 'scan':
        result = detect(Path(args.path), follow_symlinks=args.follow_symlinks)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == 'process':
        out_dir = Path(args.output_dir) if args.output_dir else _default_output_dir_for(args.path)
        result = process_path(
            Path(args.path),
            output_dir=out_dir,
            follow_symlinks=args.follow_symlinks,
            ocr_backend=args.ocr_backend,
            retry_failed_only=args.retry_failed_only,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == 'full-update':
        out_dir = Path(args.output_dir) if args.output_dir else _default_output_dir_for(args.path)
        process_result = process_path(
            Path(args.path),
            output_dir=out_dir,
            follow_symlinks=args.follow_symlinks,
            ocr_backend=args.ocr_backend,
            retry_failed_only=args.retry_failed_only,
        )
        wanted = {s.strip().lower() for s in args.markers.split(',') if s.strip()}
        selected = [m for m in MARKERS if m.key in wanted] if wanted else MARKERS
        trend_result = generate_markers_trend(
            graph_path=out_dir / 'graph.json',
            output_dir=out_dir,
            markers=selected,
        )
        print(json.dumps({
            "process": process_result,
            "markers_trend": trend_result,
        }, ensure_ascii=False, indent=2))
        return

    if args.command == 'markers-trend':
        wanted = {s.strip().lower() for s in args.markers.split(',') if s.strip()}
        selected = [m for m in MARKERS if m.key in wanted] if wanted else MARKERS
        result = generate_markers_trend(
            graph_path=Path(args.graph),
            output_dir=Path(args.output_dir),
            markers=selected,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == 'extract':
        target = Path(args.path)
        paths = collect_files(target, follow_symlinks=args.follow_symlinks) if target.is_dir() else [target]
        result = extract(paths)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == 'analyze':
        target = Path(args.path)
        paths = collect_files(target, follow_symlinks=args.follow_symlinks) if target.is_dir() else [target]
        extraction = extract(paths)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / '.graphify_extract.json').write_text(json.dumps(extraction, ensure_ascii=False, indent=2), encoding='utf-8')

        graph = build_from_json(extraction)
        communities = cluster(graph)
        cohesion = score_all(graph, communities)
        labels: dict[int, str] = {}
        for cid, node_ids in communities.items():
            sample = []
            for nid in node_ids[:3]:
                label = graph.nodes[nid].get('label', nid)
                if label not in sample:
                    sample.append(label)
            labels[cid] = ' / '.join(sample[:3]) if sample else f'Community {cid}'
        gods = god_nodes(graph)
        surprises = surprising_connections(graph, communities)
        questions = suggest_questions(graph, communities, labels)
        to_json(graph, communities, str(output_dir / 'graph.json'))
        analysis = {
            'communities': {str(k): v for k, v in communities.items()},
            'cohesion': {str(k): v for k, v in cohesion.items()},
            'gods': gods,
            'surprises': surprises,
            'questions': questions,
        }
        (output_dir / '.graphify_analysis.json').write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding='utf-8')
        (output_dir / '.graphify_labels.json').write_text(json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False, indent=2), encoding='utf-8')
        if graph.number_of_nodes() <= 5000:
            to_html(graph, communities, str(output_dir / 'graph.html'), community_labels=labels)
        detection_result = _detection_result_from_extraction(extraction, fallback_root=target)
        report_text = generate(
            graph,
            communities=communities,
            cohesion_scores=cohesion,
            community_labels=labels,
            god_node_list=gods,
            surprise_list=surprises,
            detection_result=detection_result,
            token_cost={'input': extraction.get('input_tokens', 0), 'output': extraction.get('output_tokens', 0)},
            root=str(target),
            suggested_questions=questions,
        )
        (output_dir / 'GRAPH_REPORT.md').write_text(report_text, encoding='utf-8')
        print(json.dumps({
            'nodes': graph.number_of_nodes(),
            'edges': graph.number_of_edges(),
            'communities': len(communities),
            'output_dir': str(output_dir),
        }, ensure_ascii=False, indent=2))
        return

    if args.command == 'build':
        extraction = json.loads(Path(args.path).read_text(encoding='utf-8'))
        graph = build_from_json(extraction)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        to_json(graph, {}, str(output_dir / 'graph.json'))
        print(json.dumps({
            'nodes': graph.number_of_nodes(),
            'edges': graph.number_of_edges(),
            'output_dir': str(output_dir),
        }, ensure_ascii=False, indent=2))
        return

    if args.command == 'graph-report':
        extraction = json.loads(Path(args.path).read_text(encoding='utf-8'))
        graph = build_from_json(extraction)
        communities = cluster(graph)
        cohesion = score_all(graph, communities)
        labels: dict[int, str] = {}
        for cid, node_ids in communities.items():
            sample = []
            for nid in node_ids[:3]:
                label = graph.nodes[nid].get('label', nid)
                if label not in sample:
                    sample.append(label)
            labels[cid] = ' / '.join(sample[:3]) if sample else f'Community {cid}'
        gods = god_nodes(graph)
        surprises = surprising_connections(graph, communities)
        questions = suggest_questions(graph, communities, labels)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        to_json(graph, communities, str(output_dir / 'graph.json'))
        analysis = {
            'communities': {str(k): v for k, v in communities.items()},
            'cohesion': {str(k): v for k, v in cohesion.items()},
            'gods': gods,
            'surprises': surprises,
            'questions': questions,
        }
        (output_dir / '.graphify_analysis.json').write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding='utf-8')
        (output_dir / '.graphify_labels.json').write_text(json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False, indent=2), encoding='utf-8')
        if graph.number_of_nodes() <= 5000:
            to_html(graph, communities, str(output_dir / 'graph.html'), community_labels=labels)
        detection_result = _detection_result_from_extraction(extraction)
        report_text = generate(
            graph,
            communities=communities,
            cohesion_scores=cohesion,
            community_labels=labels,
            god_node_list=gods,
            surprise_list=surprises,
            detection_result=detection_result,
            token_cost={'input': extraction.get('input_tokens', 0), 'output': extraction.get('output_tokens', 0)},
            root=str(args.path),
            suggested_questions=questions,
        )
        (output_dir / 'GRAPH_REPORT.md').write_text(report_text, encoding='utf-8')
        print(json.dumps({
            'nodes': graph.number_of_nodes(),
            'edges': graph.number_of_edges(),
            'communities': len(communities),
            'output_dir': str(output_dir),
        }, ensure_ascii=False, indent=2))
        return

    if args.command == 'add':
        saved = ingest_url(args.url, Path(args.dir), author=args.author, contributor=args.contributor)
        print(f'Saved to {saved}')
        return

    if args.command == 'query':
        graph = _load_graph(args.graph)
        terms = [t.lower() for t in args.question.split() if len(t) > 2]
        scored = _score_nodes(graph, terms)
        if not scored:
            print('No matching nodes found.')
            return
        start_nodes = [nid for _, nid in scored[:5]]
        nodes, edges = (_dfs if args.dfs else _bfs)(graph, start_nodes, depth=2)
        print(_subgraph_to_text(graph, nodes, edges, token_budget=args.budget))
        return

    if args.command == 'path':
        graph = _load_graph(args.graph)
        src_scored = _score_nodes(graph, [t.lower() for t in args.source.split()])
        tgt_scored = _score_nodes(graph, [t.lower() for t in args.target.split()])
        if not src_scored:
            print(f"No node matching '{args.source}' found.", file=sys.stderr)
            raise SystemExit(1)
        if not tgt_scored:
            print(f"No node matching '{args.target}' found.", file=sys.stderr)
            raise SystemExit(1)
        src_nid = src_scored[0][1]
        tgt_nid = tgt_scored[0][1]
        try:
            path_nodes = nx.shortest_path(graph, src_nid, tgt_nid)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            print(f"No path found between '{args.source}' and '{args.target}'.")
            return
        hops = len(path_nodes) - 1
        segments = []
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            edata = graph.edges[u, v]
            rel = edata.get('relation', '')
            conf = edata.get('confidence', '')
            conf_str = f" [{conf}]" if conf else ""
            if i == 0:
                segments.append(graph.nodes[u].get('label', u))
            segments.append(f"--{rel}{conf_str}--> {graph.nodes[v].get('label', v)}")
        print(f"Shortest path ({hops} hops):\n  " + " ".join(segments))
        return

    if args.command == 'explain':
        graph = _load_graph(args.graph)
        matches = [nid for _, nid in _score_nodes(graph, [t.lower() for t in args.label.split()])]
        if not matches:
            print(f"No node matching '{args.label}' found.")
            return
        nid = matches[0]
        data = graph.nodes[nid]
        print(f"Node: {data.get('label', nid)}")
        print(f"  ID:        {nid}")
        source_file = data.get('source_file', '')
        print(f"  Source:    {source_file} {data.get('source_location', '')}".rstrip())
        print(f"  Type:      {data.get('file_type', '')}")
        bucket = _medical_bucket_line(source_file)
        if bucket:
            print(f"  Medical Bucket: {bucket}")
        print(f"  Community: {data.get('community', '')}")
        print(f"  Degree:    {graph.degree(nid)}")
        neighbors = list(graph.neighbors(nid))
        if neighbors:
            print(f"\nConnections ({len(neighbors)}):")
            for nb in sorted(neighbors, key=lambda n: graph.degree(n), reverse=True)[:20]:
                edata = graph.edges[nid, nb]
                rel = edata.get('relation', '')
                conf = edata.get('confidence', '')
                print(f"  --> {graph.nodes[nb].get('label', nb)} [{rel}] [{conf}]")
        return

    if args.command == 'serve':
        serve_graph(args.graph)
        return

    if args.command == 'wiki':
        graph = _load_graph(args.graph)
        communities = _communities_from_graph(graph)
        labels = {cid: f"Community {cid}" for cid in communities}
        articles = to_wiki(graph, communities, args.output_dir, community_labels=labels, god_nodes_data=god_nodes(graph))
        print(json.dumps({
            'articles': articles,
            'output_dir': str(args.output_dir),
        }, ensure_ascii=False, indent=2))
        return

    if args.command == 'graphml':
        graph = _load_graph(args.graph)
        communities = _communities_from_graph(graph)
        to_graphml(graph, communities, args.output)
        print(json.dumps({
            'nodes': graph.number_of_nodes(),
            'edges': graph.number_of_edges(),
            'output': str(args.output),
        }, ensure_ascii=False, indent=2))
        return

    if args.command == 'obsidian':
        graph = _load_graph(args.graph)
        communities = _communities_from_graph(graph)
        labels = {cid: f"Community {cid}" for cid in communities}
        note_count = to_obsidian(graph, communities, args.output_dir, community_labels=labels)
        print(json.dumps({
            'notes': note_count,
            'output_dir': str(args.output_dir),
        }, ensure_ascii=False, indent=2))
        return

    if args.command == 'neo4j':
        graph = _load_graph(args.graph)
        to_cypher(graph, args.output)
        print(json.dumps({
            'nodes': graph.number_of_nodes(),
            'edges': graph.number_of_edges(),
            'output': str(args.output),
        }, ensure_ascii=False, indent=2))
        return

    if args.command == 'neo4j-push':
        graph = _load_graph(args.graph)
        communities = _communities_from_graph(graph)
        pushed = push_to_neo4j(
            graph,
            uri=args.uri,
            user=args.user,
            password=args.password,
            communities=communities,
        )
        print(json.dumps(pushed, ensure_ascii=False, indent=2))
        return

    if args.command == 'hook':
        if args.action == 'install':
            print(hook_install(Path('.')))
        elif args.action == 'uninstall':
            print(hook_uninstall(Path('.')))
        else:
            print(hook_status(Path('.')))
        return

    if args.command == 'report':
        result = detect(Path(args.path))
        target = write_medical_summary_report(result, args.path, args.output_dir)
        print(target)
        return

    if args.command == 'update':
        result = detect_incremental(Path(args.path), manifest_path=args.manifest_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == 'backfill-merge':
        result = merge_backfill_files(Path(args.path), chunks_glob=args.chunks_glob, chunk_plan=args.chunk_plan)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == 'watch':
        watch_folder(Path(args.path), debounce=args.debounce)
        return

    parser.print_help()


if __name__ == '__main__':
    main()
