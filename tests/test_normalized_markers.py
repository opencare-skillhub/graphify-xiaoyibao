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


def test_extract_text_not_using_marker_digits_as_value() -> None:
    text = """
    报告日期：2025-03-06
    糖类抗原CA125参考值：0-35U/mL 7.28U/mL
    """
    rows = extract_marker_records_from_texts([("raw/Picsew_20250306153026.JPEG", text)])
    ca125 = [r for r in rows if r["marker_key"] == "ca125"]
    assert ca125
    assert abs(ca125[0]["value"] - 7.28) < 1e-6


def test_extract_text_panel_sections_split_source_file() -> None:
    text = """
    [[PANEL:1]]
    报告日期：2025-03-06
    糖类抗原19-9(高值)参考值：0.00-27.00U/ml 15.70U/ml
    [[PANEL:2]]
    报告日期：2025-03-06
    糖类抗原19-9 参考值：0-27U/mL 16.60U/ml
    """
    rows = extract_marker_records_from_texts([("raw/Picsew_20250306153026.JPEG", text)])
    ca = [r for r in rows if r["marker_key"] == "ca19_9"]
    assert len(ca) == 2
    assert any("#panel1" in r["source_file"] for r in ca)
    assert any("#panel2" in r["source_file"] for r in ca)
