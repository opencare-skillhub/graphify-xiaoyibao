from xyb.normalized import extract_marker_records_from_nodes, extract_marker_records_from_texts


def test_extract_from_texts_prefers_result_over_reference_range() -> None:
    text = """
    检验日期：2026-03-31
    CA19-9 结果 28.9 U/mL 参考范围 0-37 U/mL
    """
    rows = extract_marker_records_from_texts([("raw/IMG_6301.png", text)])
    ca = [r for r in rows if r["marker_key"] == "ca19_9"]
    assert ca
    assert abs(ca[0]["value"] - 28.9) < 1e-6


def test_extract_from_nodes_skips_reference_range_like_value() -> None:
    nodes = [
        {"id": "n1", "label": "CA19-9 参考范围 0-37 U/mL", "source_file": "raw/a.png"},
        {"id": "n2", "label": "CA19-9 结果 45.2 U/mL", "source_file": "raw/b_20260331.png"},
    ]
    rows = extract_marker_records_from_nodes(nodes)
    assert not [r for r in rows if r["source_file"] == "raw/a.png"]
    ok = [r for r in rows if r["source_file"] == "raw/b_20260331.png"]
    assert ok and abs(ok[0]["value"] - 45.2) < 1e-6


def test_extract_text_accepts_value_before_marker_when_layout_reordered() -> None:
    text = """
    报告日期：2026-03-31
    28.90U/ml 糖链抗原19-9(高值)参考值：0.00-27.00U/ml
    """
    rows = extract_marker_records_from_texts([("raw/IMG_6301.png", text)])
    ca = [r for r in rows if r["marker_key"] == "ca19_9"]
    assert ca and abs(ca[0]["value"] - 28.9) < 1e-6
