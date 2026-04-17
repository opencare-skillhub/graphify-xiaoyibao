from __future__ import annotations

import subprocess
import sys


def test_python_module_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', '--help'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'xyb' in result.stdout.lower()
