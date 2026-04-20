from __future__ import annotations

import json

from xyb.mineru_batch import _mineru_structured_text_from_json
from xyb.normalized import extract_marker_records_from_texts


def test_mineru_content_list_rebuild_keeps_row_order_for_ca199() -> None:
    payload = [
        {"type": "text", "text": "申请科室：胰腺门诊 报告日期：2026-3-31 0:00:00", "bbox": [10, 10, 600, 40], "page_idx": 0},
        {"type": "text", "text": "糖链抗原242 参考值：0-20U/ml", "bbox": [20, 300, 420, 330], "page_idx": 0},
        {"type": "text", "text": "12.50U/ml", "bbox": [720, 300, 920, 330], "page_idx": 0},
        {"type": "text", "text": "糖链抗原50 参考值：0-25IU/ml", "bbox": [20, 350, 420, 380], "page_idx": 0},
        {"type": "text", "text": "14.40IU/mL", "bbox": [720, 350, 920, 380], "page_idx": 0},
        {"type": "text", "text": "糖链抗原19-9(高值) 参考值：0.00-27.00U/ml", "bbox": [20, 400, 520, 430], "page_idx": 0},
        {"type": "text", "text": "28.90U/ml", "bbox": [720, 400, 920, 430], "page_idx": 0},
    ]
    text = _mineru_structured_text_from_json(json.dumps(payload, ensure_ascii=False))
    rows = extract_marker_records_from_texts([("raw/IMG_6301.PNG", text)])
    ca = [r for r in rows if r["marker_key"] == "ca19_9"]
    assert ca
    assert abs(ca[0]["value"] - 28.9) < 1e-6

