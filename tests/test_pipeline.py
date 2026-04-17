from __future__ import annotations

from pathlib import Path

from xyb.detect import detect


def test_detect_pipeline_smoke(tmp_path: Path) -> None:
    (tmp_path / 'note.md').write_text('# note\n\nhello', encoding='utf-8')
    detected = detect(tmp_path)
    assert detected['total_files'] >= 1
