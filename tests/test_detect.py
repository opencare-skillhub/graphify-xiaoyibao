from __future__ import annotations

from pathlib import Path

from xyb.detect import classify_file, detect


def test_classify_medical_files(tmp_path: Path) -> None:
    assert classify_file(tmp_path / 'a.pdf').value in {'paper', 'document'}
    assert classify_file(tmp_path / 'a.png').value == 'image'
    assert classify_file(tmp_path / 'a.docx').value == 'document'


def test_detect_supports_medical_assets(tmp_path: Path) -> None:
    assert classify_file(tmp_path / 'scan.heic').value == 'image'
    assert classify_file(tmp_path / 'study.dcm').value == 'dicom'


def test_detect_reports_medical_directory_hits(tmp_path: Path) -> None:
    target = tmp_path / '05_影像资料' / 'CT'
    target.mkdir(parents=True)
    (target / 'scan.png').write_bytes(b'img')
    result = detect(tmp_path)
    assert result['medical_directory_hits']['imaging'] >= 1
