from __future__ import annotations

from xyb.build import build_from_json
from xyb.report import generate, generate_medical_summary


def test_generate_report_includes_summary() -> None:
    graph = build_from_json({'nodes': [], 'edges': [], 'hyperedges': []})
    text = generate(
        graph,
        communities={},
        cohesion_scores={},
        community_labels={},
        god_node_list=[],
        surprise_list=[],
        detection_result={'total_files': 0, 'total_words': 0, 'warning': None},
        token_cost={'input': 0, 'output': 0},
        root='.',
        suggested_questions=None,
    )
    assert '# Graph Report - .' in text
    assert '## Summary' in text


def test_generate_medical_summary_mentions_template_guidance() -> None:
    text = generate_medical_summary({'total_files': 1, 'total_words': 10, 'files': {}, 'medical_directory_hits': {}}, '.')
    assert 'xyb init' in text
    assert '病情资料概览' in text


def test_generate_medical_summary_mentions_missing_priority_buckets() -> None:
    text = generate_medical_summary({
        'total_files': 2,
        'total_words': 100,
        'files': {'document': ['a.md']},
        'medical_directory_hits': {'diagnosis': 1},
    }, '.')
    assert '关键资料完整度' in text
    assert '已覆盖：diagnosis' in text
    assert '待补充：treatment, imaging, labs_markers' in text
