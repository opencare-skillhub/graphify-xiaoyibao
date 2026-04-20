from xyb.facts_extractor import (
    extract_medical_facts,
    observation_facts_to_marker_records,
    split_panel_sections,
)


def test_split_panel_sections() -> None:
    text = "[[PANEL:1]]\naaa\n[[PANEL:2]]\nbbb\n"
    out = split_panel_sections(text)
    assert out == [("1", "aaa"), ("2", "bbb")]


def test_extract_medical_facts_rule_mode() -> None:
    text = """
    报告日期：2025-03-06
    糖类抗原CA125参考值：0-35U/mL 7.28U/mL
    糖类抗原19-9(高值)参考值：0.00-27.00U/ml 15.70U/ml
    """
    facts = extract_medical_facts([("raw/a.jpeg", text)], mode="rule")
    obs = facts["observation_facts"]
    assert obs
    keys = {o["item_code"] for o in obs}
    assert "ca125" in keys
    assert "ca19_9" in keys


def test_observation_facts_to_marker_records() -> None:
    records = observation_facts_to_marker_records(
        [
            {
                "report_date": "2025-03-06",
                "item_code": "ca19_9",
                "item_name": "CA19-9",
                "value": 15.7,
                "unit": "U/mL",
                "source_file": "raw/a.jpeg",
            }
        ]
    )
    assert records and records[0]["marker_key"] == "ca19_9"


def test_extract_medical_facts_contains_diagnosis_fallback() -> None:
    text = """
    报告日期：2026-04-28
    检查所见：胰头不规则肿块，范围较前相仿。
    影像诊断：腹膜网膜多发结节。
    """
    facts = extract_medical_facts([("raw/ct_report.png", text)], mode="rule")
    dx = facts["diagnosis_facts"]
    assert dx
    assert "胰头不规则肿块" in (dx[0].get("finding") or "")


def test_extract_medical_facts_rule_mode_linewise_binding_for_marker_panel() -> None:
    text = """
    报告日期：2025-7-10 0:00:00
    癌胚抗原参考值：0-5.20 ng/ml
    6.90ng/ml
    甲胎蛋白参考值：0-10.00 ng/ml
    2.79ng/ml
    糖类抗原CA125参考值：0-35U/mL
    7.12U/ml
    糖类抗原19-9 参考值：0-27 U/mL
    18.60U/ml
    糖类抗原50参考值：0-25IU/ml
    11.10IU/mL
    糖类抗原72-4参考值：0-6.90 U/ml
    47.40U/ml
    糖类抗原242参考值：0-20 U/ml
    9.86U/ml
    """
    facts = extract_medical_facts([("raw/IMG_3119.md", text)], mode="rule")
    obs = facts["observation_facts"]
    got = {o["item_code"]: float(o["value"]) for o in obs}
    assert got["cea"] == 6.9
    assert got["afp"] == 2.79
    assert got["ca125"] == 7.12
    assert got["ca19_9"] == 18.6
    assert got["ca50"] == 11.1
    assert got["ca72_4"] == 47.4
    assert got["ca242"] == 9.86
