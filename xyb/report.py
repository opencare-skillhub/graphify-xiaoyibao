# generate GRAPH_REPORT.md - the human-readable audit trail
from __future__ import annotations
import re
from datetime import date
from pathlib import Path
import networkx as nx


_PRIORITY_MEDICAL_BUCKETS = ['diagnosis', 'treatment', 'imaging', 'labs_markers']


def _safe_community_name(label: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|#^[\]]', "", label.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")).strip()
    cleaned = re.sub(r"\.(md|mdx|markdown)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned or "unnamed"


def generate_medical_summary(detection_result: dict, root: str | Path) -> str:
    root = str(root)
    hits = detection_result.get('medical_directory_hits', {})
    covered_priority = [bucket for bucket in _PRIORITY_MEDICAL_BUCKETS if hits.get(bucket)]
    missing_priority = [bucket for bucket in _PRIORITY_MEDICAL_BUCKETS if not hits.get(bucket)]
    lines = [
        f"# 病情资料概览 - {root}",
        "",
        "## 扫描摘要",
        f"- 总文件数：{detection_result.get('total_files', 0)}",
        f"- 估计总词数：{detection_result.get('total_words', 0):,}",
    ]
    if detection_result.get('warning'):
        lines.append(f"- 提示：{detection_result['warning']}")

    lines += ["", "## 病情目录命中"]
    if hits:
        for key, value in sorted(hits.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- 未命中官方病情目录模板分组；系统仍可扫描，但建议使用 `xyb init` 初始化目录模板。")

    lines += ["", "## 关键资料完整度"]
    lines.append(f"- 已覆盖：{', '.join(covered_priority) if covered_priority else '无'}")
    lines.append(f"- 待补充：{', '.join(missing_priority) if missing_priority else '无'}")

    files = detection_result.get('files', {})
    lines += ["", "## 文件类型统计"]
    for file_type in ['paper', 'document', 'image', 'video', 'code']:
        lines.append(f"- {file_type}: {len(files.get(file_type, []))}")

    lines += ["", "## 建议"]
    if missing_priority:
        lines.append(f"- 建议优先补齐：{' / '.join(missing_priority)}。")
    else:
        lines.append("- 关键四类资料已有命中，可继续补充随访、营养、心理与风险管理资料。")
    lines.append("- 子目录可以继续保留多层结构，`xyb scan` 默认递归扫描。")
    lines.append("- 若资料仍较散，可先执行 `xyb init` 生成模板目录，再把现有文件搬入相应分组。")
    return "\n".join(lines)


def write_medical_summary_report(detection_result: dict, root: str | Path, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / 'MEDICAL_SUMMARY.md'
    target.write_text(generate_medical_summary(detection_result, root), encoding='utf-8')
    return target


def generate(
    G: nx.Graph,
    communities: dict[int, list[str]],
    cohesion_scores: dict[int, float],
    community_labels: dict[int, str],
    god_node_list: list[dict],
    surprise_list: list[dict],
    detection_result: dict,
    token_cost: dict,
    root: str,
    suggested_questions: list[dict] | None = None,
) -> str:
    today = date.today().isoformat()

    confidences = [d.get("confidence", "EXTRACTED") for _, _, d in G.edges(data=True)]
    total = len(confidences) or 1
    ext_pct = round(confidences.count("EXTRACTED") / total * 100)
    inf_pct = round(confidences.count("INFERRED") / total * 100)
    amb_pct = round(confidences.count("AMBIGUOUS") / total * 100)

    inf_edges = [(u, v, d) for u, v, d in G.edges(data=True) if d.get("confidence") == "INFERRED"]
    inf_scores = [d.get("confidence_score", 0.5) for _, _, d in inf_edges]
    inf_avg = round(sum(inf_scores) / len(inf_scores), 2) if inf_scores else None

    lines = [f"# Graph Report - {root}  ({today})", "", "## Corpus Check"]
    if detection_result.get("warning"):
        lines.append(f"- {detection_result['warning']}")
    else:
        lines += [
            f"- {detection_result['total_files']} files · ~{detection_result['total_words']:,} words",
            "- Verdict: corpus is large enough that graph structure adds value.",
        ]

    medical_hits = detection_result.get('medical_directory_hits', {})
    if medical_hits:
        lines += ["", "## Medical Record Layout Signals"]
        for key, value in sorted(medical_hits.items()):
            lines.append(f"- {key}: {value}")

    lines += [
        "",
        "## Summary",
        f"- {G.number_of_nodes()} nodes · {G.number_of_edges()} edges · {len(communities)} communities detected",
        f"- Extraction: {ext_pct}% EXTRACTED · {inf_pct}% INFERRED · {amb_pct}% AMBIGUOUS"
        + (f" · INFERRED: {len(inf_edges)} edges (avg confidence: {inf_avg})" if inf_avg is not None else ""),
        f"- Token cost: {token_cost.get('input', 0):,} input · {token_cost.get('output', 0):,} output",
    ]

    if communities:
        lines += ["", "## Community Hubs (Navigation)"]
        for cid in communities:
            label = community_labels.get(cid, f"Community {cid}")
            safe = _safe_community_name(label)
            lines.append(f"- [[_COMMUNITY_{safe}|{label}]]")

    lines += ["", "## God Nodes (most connected - your core abstractions)"]
    for i, node in enumerate(god_node_list, 1):
        lines.append(f"{i}. `{node['label']}` - {node['edges']} edges")

    lines += ["", "## Surprising Connections (you probably didn't know these)"]
    if surprise_list:
        for s in surprise_list:
            relation = s.get("relation", "related_to")
            note = s.get("note", "")
            files = s.get("source_files", ["", ""])
            conf = s.get("confidence", "EXTRACTED")
            cscore = s.get("confidence_score")
            conf_tag = f"INFERRED {cscore:.2f}" if conf == "INFERRED" and cscore is not None else conf
            sem_tag = " [semantically similar]" if relation == "semantically_similar_to" else ""
            lines += [
                f"- `{s['source']}` --{relation}--> `{s['target']}`  [{conf_tag}]{sem_tag}",
                f"  {files[0]} → {files[1]}" + (f"  _{note}_" if note else ""),
            ]
    else:
        lines.append("- None detected - all connections are within the same source files.")

    hyperedges = G.graph.get("hyperedges", [])
    if hyperedges:
        lines += ["", "## Hyperedges (group relationships)"]
        for h in hyperedges:
            node_labels = ", ".join(h.get("nodes", []))
            conf = h.get("confidence", "INFERRED")
            cscore = h.get("confidence_score")
            conf_tag = f"{conf} {cscore:.2f}" if cscore is not None else conf
            lines.append(f"- **{h.get('label', h.get('id', ''))}** — {node_labels} [{conf_tag}]")

    lines += ["", "## Communities"]
    from .analyze import _is_file_node as _ifn
    for cid, nodes in communities.items():
        label = community_labels.get(cid, f"Community {cid}")
        score = cohesion_scores.get(cid, 0.0)
        real_nodes = [n for n in nodes if not _ifn(G, n)]
        display = [G.nodes[n].get("label", n) for n in real_nodes[:8]]
        suffix = f" (+{len(real_nodes)-8} more)" if len(real_nodes) > 8 else ""
        lines += ["", f"### Community {cid} - \"{label}\"", f"Cohesion: {score}", f"Nodes ({len(real_nodes)}): {', '.join(display)}{suffix}"]

    ambiguous = [(u, v, d) for u, v, d in G.edges(data=True) if d.get("confidence") == "AMBIGUOUS"]
    if ambiguous:
        lines += ["", "## Ambiguous Edges - Review These"]
        for u, v, d in ambiguous:
            ul = G.nodes[u].get("label", u)
            vl = G.nodes[v].get("label", v)
            lines += [f"- `{ul}` → `{vl}`  [AMBIGUOUS]", f"  {d.get('source_file', '')} · relation: {d.get('relation', 'unknown')}"]

    from .analyze import _is_file_node, _is_concept_node
    isolated = [n for n in G.nodes() if G.degree(n) <= 1 and not _is_file_node(G, n) and not _is_concept_node(G, n)]
    thin_communities = {cid: nodes for cid, nodes in communities.items() if len(nodes) < 3}
    gap_count = len(isolated) + len(thin_communities)
    if gap_count > 0 or amb_pct > 20:
        lines += ["", "## Knowledge Gaps"]
        if isolated:
            isolated_labels = [G.nodes[n].get("label", n) for n in isolated[:5]]
            suffix = f" (+{len(isolated)-5} more)" if len(isolated) > 5 else ""
            lines.append(f"- **{len(isolated)} isolated node(s):** {', '.join(f'`{l}`' for l in isolated_labels)}{suffix}")
            lines.append("  These have ≤1 connection - possible missing edges or undocumented components.")
        if thin_communities:
            for cid, nodes in thin_communities.items():
                label = community_labels.get(cid, f"Community {cid}")
                node_labels = [G.nodes[n].get("label", n) for n in nodes]
                lines.append(f"- **Thin community `{label}`** ({len(nodes)} nodes): {', '.join(f'`{l}`' for l in node_labels)}")
                lines.append("  Too small to be a meaningful cluster - may be noise or needs more connections extracted.")
        if amb_pct > 20:
            lines.append(f"- **High ambiguity: {amb_pct}% of edges are AMBIGUOUS.** Review the Ambiguous Edges section above.")

    if suggested_questions:
        lines += ["", "## Suggested Questions"]
        no_signal = len(suggested_questions) == 1 and suggested_questions[0].get("type") == "no_signal"
        if no_signal:
            lines.append(f"_{suggested_questions[0]['why']}_")
        else:
            lines.append("_Questions this graph is uniquely positioned to answer:_")
            lines.append("")
            for q in suggested_questions:
                if q.get("question"):
                    lines.append(f"- **{q['question']}**")
                    lines.append(f"  _{q['why']}_")

    return "\n".join(lines)
