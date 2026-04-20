from pathlib import Path

from xyb.validation import validate_marker_records, write_validation_outputs


def test_validate_marker_records_marks_conflict() -> None:
    rows = [
        {"source_file": "a.png", "date": "2026-03-31", "marker_key": "ca19_9", "value": 28.9, "unit": "U/mL"},
        {"source_file": "a.png", "date": "2026-03-31", "marker_key": "ca19_9", "value": 88.9, "unit": "U/mL"},
    ]
    validated, conflicts, review, summary = validate_marker_records(rows)
    assert summary["conflict"] == 2
    assert conflicts
    assert not review
    assert all(r["status"] == "conflict" for r in validated)


def test_write_validation_outputs(tmp_path: Path) -> None:
    out = write_validation_outputs(
        tmp_path,
        validated=[{"a": 1, "status": "ok"}],
        conflicts=[{"a": 2}],
        review=[{"a": 3}],
        summary={"total": 1, "ok": 1, "conflict": 0, "review_needed": 0},
    )
    assert Path(out["validated_file"]).exists()
    assert Path(out["conflicts_file"]).exists()
    assert Path(out["review_file"]).exists()
    assert Path(out["report_file"]).exists()

