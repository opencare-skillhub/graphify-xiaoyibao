from __future__ import annotations

import json
from pathlib import Path


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

