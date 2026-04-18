from __future__ import annotations

from xyb.process import _extract_image_medical_concepts


def test_extract_image_medical_concepts_prefers_result_not_reference() -> None:
    text = """
报告日期：2026-3-31 0:00:00
癌胚抗原
参考值：0-5.20 ng/ml
8.08ng/ml
糖链抗原125
参考值：0-35 U/mL
6.38U/ml
糖链抗原15-3
参考值：0.00-25.00U/ml
11.10U/ml
糖链抗原72-4
参考值：0-6.90 U/ml
3.46 U/ml
糖链抗原242
参考值：0-20 U/ml
12.50U/ml
糖链抗原50
参考值：0-25 IU/ml
14.40 IU/mL
糖链抗原19-9(高值)
参考值：0.00-27.00U/ml
28.90U/ml
"""
    concepts = _extract_image_medical_concepts(text)
    assert "CEA 8.08 ng/mL" in concepts
    assert "CA125 6.38 U/mL" in concepts
    assert "CA15-3 11.10 U/mL" in concepts
    assert "CA72-4 3.46 U/mL" in concepts
    assert "CA242 12.50 U/mL" in concepts
    assert "CA50 14.40 IU/mL" in concepts
    assert "CA19-9 28.90 U/mL" in concepts
    assert "CA125 35 U/mL" not in concepts
    assert "CA19-9 27.00 U/mL" not in concepts


def test_extract_image_medical_concepts_ct_keywords() -> None:
    text = """
检查方法：对比前片2026-01-06：胰头不规则肿块
腹膜网膜、肝包膜多发强化结节
# 放射学诊断
胰头MT范围较前相仿，腹膜广泛转移灶
胆囊结石可能同前
"""
    concepts = _extract_image_medical_concepts(text)
    assert "放射学诊断" in concepts
    assert "胰头" in concepts
    assert "腹膜" in concepts
    assert "肝包膜" in concepts
    assert "转移" in concepts
    assert "胆囊结石" in concepts
