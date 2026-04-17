from __future__ import annotations

import subprocess
import sys


def test_xyb_init_creates_template_tree(tmp_path) -> None:
    target = tmp_path / 'records'
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', 'init', str(target)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (target / '00_说明与索引').exists()
    assert (target / 'README_如何整理.md').exists()
