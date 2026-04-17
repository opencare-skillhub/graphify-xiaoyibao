from __future__ import annotations

from xyb.ingest import _safe_filename
from xyb.security import validate_url


def test_safe_filename_from_url() -> None:
    name = _safe_filename('https://example.com/a/b', '.md')
    assert name.endswith('.md')
    assert 'example' in name


def test_validate_url_blocks_file_scheme() -> None:
    try:
        validate_url('file:///tmp/x')
    except ValueError as exc:
        assert 'only http and https are allowed' in str(exc)
    else:
        raise AssertionError('validate_url should reject file:// URLs')
