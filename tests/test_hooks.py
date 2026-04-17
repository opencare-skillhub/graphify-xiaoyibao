from __future__ import annotations

from xyb.hooks import install, status, uninstall


def test_hook_install_status_uninstall(tmp_path) -> None:
    repo = tmp_path / 'repo'
    hooks_dir = repo / '.git' / 'hooks'
    hooks_dir.mkdir(parents=True)

    msg = install(repo)
    assert 'post-commit:' in msg
    assert (hooks_dir / 'post-commit').exists()
    assert (hooks_dir / 'post-checkout').exists()

    st = status(repo)
    assert 'post-commit: installed' in st
    assert 'post-checkout: installed' in st

    rm = uninstall(repo)
    assert 'post-commit:' in rm
    assert 'post-checkout:' in rm
