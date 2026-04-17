from __future__ import annotations

from pathlib import Path

from xyb_core.report.render import render_report


def test_render_report_writes_markdown(tmp_path: Path) -> None:
    profile = {
        "basic_info": {"name": "张三"},
        "diagnosis_info": {"stage": "IV"},
        "treatment_history": [],
        "nutrition": {},
        "psychology_scores": [],
    }
    target = render_report(profile=profile, format="md", output_dir=tmp_path)
    text = target.read_text(encoding="utf-8")
    assert "# 病情概览 - 张三" in text
    assert "## 确诊信息" in text
