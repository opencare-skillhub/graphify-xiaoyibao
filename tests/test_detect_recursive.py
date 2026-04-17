from __future__ import annotations

from xyb.detect import detect
from xyb.extract import collect_files


def test_detect_scans_nested_subdirectories(tmp_path) -> None:
    nested = tmp_path / 'a' / 'b' / 'c'
    nested.mkdir(parents=True)
    (nested / 'report.pdf').write_bytes(b'%PDF-1.4')
    result = detect(tmp_path)
    assert result['total_files'] >= 1
    assert any(path.endswith('report.pdf') for path in result['files']['paper'])


def test_detect_skips_noise_directories(tmp_path) -> None:
    noise = tmp_path / '.venv'
    noise.mkdir(parents=True)
    (noise / 'secret.md').write_text('hidden', encoding='utf-8')
    real = tmp_path / 'raw'
    real.mkdir()
    (real / 'note.md').write_text('hello', encoding='utf-8')
    result = detect(tmp_path)
    all_paths = sum(result['files'].values(), [])
    assert any(path.endswith('note.md') for path in all_paths)
    assert not any(path.endswith('secret.md') for path in all_paths)


def test_extract_collect_files_skips_archive_and_graphify_out(tmp_path) -> None:
    root = tmp_path / 'workspace'
    (root / 'src').mkdir(parents=True)
    (root / 'docs' / 'archive').mkdir(parents=True)
    (root / 'graphify-out').mkdir(parents=True)
    (root / 'src' / 'main.py').write_text('print("ok")\n', encoding='utf-8')
    (root / 'docs' / 'archive' / 'old.py').write_text('print("old")\n', encoding='utf-8')
    (root / 'graphify-out' / 'cached.py').write_text('print("cache")\n', encoding='utf-8')

    files = collect_files(root)
    names = {str(p.relative_to(root)) for p in files}
    assert 'src/main.py' in names
    assert 'docs/archive/old.py' not in names
    assert 'graphify-out/cached.py' not in names
