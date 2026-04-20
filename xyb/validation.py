from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


def validate_marker_records(records: list[dict], *, progress_cb=None) -> tuple[list[dict], list[dict], list[dict], dict]:
    total = len(records)
    validated: list[dict] = []
    conflicts: list[dict] = []
    review: list[dict] = []

    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for r in records:
        key = (str(r.get("source_file", "")), str(r.get("date", "")), str(r.get("marker_key", "")))
        grouped.setdefault(key, []).append(r)

    conflict_keys: set[tuple[str, str, str]] = set()
    for key, rows in grouped.items():
        vals = sorted({float(x.get("value", 0.0)) for x in rows if isinstance(x.get("value"), (int, float))})
        if len(vals) <= 1:
            continue
        if (max(vals) - min(vals)) >= max(2.0, 0.15 * max(vals)):
            conflict_keys.add(key)
            conflicts.append({
                "source_file": key[0],
                "date": key[1],
                "marker_key": key[2],
                "values": vals,
                "reason": "multiple divergent values in same file/date/marker",
            })

    for i, row in enumerate(records, start=1):
        if progress_cb:
            progress_cb(i, total)
        r = dict(row)
        flags: list[str] = []
        status = "ok"

        if not r.get("date"):
            flags.append("missing_date")
        if not isinstance(r.get("value"), (int, float)):
            flags.append("invalid_value")
        else:
            v = float(r.get("value"))
            if v <= 0:
                flags.append("non_positive_value")
            if v > 100000:
                flags.append("extreme_value")

        rk = (str(r.get("source_file", "")), str(r.get("date", "")), str(r.get("marker_key", "")))
        if rk in conflict_keys:
            status = "conflict"
            flags.append("divergent_values")
        elif flags:
            status = "review_needed"

        r["status"] = status
        if flags:
            r["validation_flags"] = flags
        validated.append(r)
        if status == "review_needed":
            review.append(r)

    summary = {
        "total": total,
        "ok": sum(1 for r in validated if r.get("status") == "ok"),
        "conflict": sum(1 for r in validated if r.get("status") == "conflict"),
        "review_needed": sum(1 for r in validated if r.get("status") == "review_needed"),
    }
    return validated, conflicts, review, summary


def write_validation_outputs(output_dir: Path, validated: list[dict], conflicts: list[dict], review: list[dict], summary: dict) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    validated_path = output_dir / "markers_validated.jsonl"
    conflicts_path = output_dir / "validation_conflicts.jsonl"
    review_path = output_dir / "review_queue.jsonl"
    report_path = output_dir / "validation_report.json"

    with validated_path.open("w", encoding="utf-8") as f:
        for row in validated:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with conflicts_path.open("w", encoding="utf-8") as f:
        for row in conflicts:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with review_path.open("w", encoding="utf-8") as f:
        for row in review:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    report = {
        **summary,
        "validated_file": str(validated_path.resolve()),
        "conflicts_file": str(conflicts_path.resolve()),
        "review_file": str(review_path.resolve()),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "validated_file": str(validated_path.resolve()),
        "conflicts_file": str(conflicts_path.resolve()),
        "review_file": str(review_path.resolve()),
        "report_file": str(report_path.resolve()),
        **summary,
    }


def resolve_conflicts_with_llm(
    conflicts: list[dict],
    *,
    text_by_source: dict[str, str],
    progress_cb=None,
) -> list[dict]:
    """
    对 conflict 条目进行 LLM 局部复核（文本级）。
    仅在 OPENAI_COMPAT_* 可用时执行。
    """
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    api_key = os.getenv("OPENAI_COMPAT_API_KEY", "")
    model = os.getenv("OPENAI_COMPAT_MODEL", "")
    if not base_url or not api_key or not model:
        return []

    out: list[dict] = []
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    total = len(conflicts)
    for i, c in enumerate(conflicts, start=1):
        if progress_cb:
            progress_cb(i, total)
        source_file = str(c.get("source_file", ""))
        marker_key = str(c.get("marker_key", ""))
        date = str(c.get("date", ""))
        values = c.get("values", [])
        text = text_by_source.get(source_file, "")
        prompt = (
            "你是医疗检验单结构化复核助手。"
            "请在给定文本中，只判断该 marker 的真实结果值（不是参考范围）。"
            "若无法判断返回 null。"
            "输出严格 JSON：{\"resolved_value\": number|null, \"reason\": string, \"confidence\": \"high|medium|low\"}"
            f"\nmarker_key={marker_key}\ndate={date}\ncandidates={values}\ntext:\n{text[:3000]}"
        )
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        try:
            r = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=90)
            r.raise_for_status()
            body = r.json()
            content = str(body["choices"][0]["message"]["content"]).strip()
            # 容错提取 json 对象
            start = content.find("{")
            end = content.rfind("}")
            parsed = json.loads(content[start : end + 1]) if start >= 0 and end > start else {}
            out.append(
                {
                    "source_file": source_file,
                    "date": date,
                    "marker_key": marker_key,
                    "values": values,
                    "resolved_value": parsed.get("resolved_value"),
                    "reason": parsed.get("reason", ""),
                    "confidence": parsed.get("confidence", "low"),
                }
            )
        except Exception as exc:
            out.append(
                {
                    "source_file": source_file,
                    "date": date,
                    "marker_key": marker_key,
                    "values": values,
                    "resolved_value": None,
                    "reason": f"llm_error: {repr(exc)}",
                    "confidence": "low",
                }
            )
    return out
