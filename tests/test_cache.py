from __future__ import annotations

from pathlib import Path

from xyb.cache import file_hash


def test_file_hash_changes_when_body_changes(tmp_path: Path) -> None:
    path = tmp_path / 'note.md'
    path.write_text('---\ntitle: a\n---\n\nhello', encoding='utf-8')
    first = file_hash(path, tmp_path)
    path.write_text('---\ntitle: a\n---\n\nworld', encoding='utf-8')
    second = file_hash(path, tmp_path)
    assert first != second
