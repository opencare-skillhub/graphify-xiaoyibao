from __future__ import annotations

from pathlib import Path


def render_report(*, profile: dict, format: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    patient_name = profile.get("basic_info", {}).get("name", "未命名")
    diagnosis_info = profile.get("diagnosis_info", {})

    if format == "md":
        target = output_dir / "report.md"
        target.write_text(
            f"# 病情概览 - {patient_name}\n\n## 确诊信息\n\n{diagnosis_info}\n",
            encoding="utf-8",
        )
        return target
    if format == "html":
        target = output_dir / "report.html"
        target.write_text(
            f"<html><body><h1>病情概览 - {patient_name}</h1></body></html>",
            encoding="utf-8",
        )
        return target

    target = output_dir / "report.pdf"
    target.write_bytes(b"%PDF-1.4\n%xyb\n")
    return target
