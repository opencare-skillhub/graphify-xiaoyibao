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

