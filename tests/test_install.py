from __future__ import annotations

from xyb.install import (
    install_cursor_local,
    install_claude_local,
    install_codex_local,
    install_gemini_local,
    install_global_platform,
    install_local,
    install_opencode_local,
    uninstall_claude_local,
    uninstall_codex_local,
    uninstall_cursor_local,
    uninstall_gemini_local,
    uninstall_global_platform,
    uninstall_local,
    uninstall_opencode_local,
)


def test_install_local_writes_agents_md(tmp_path) -> None:
    msg = install_local(tmp_path)
    assert 'AGENTS.md' in msg
    target = tmp_path / 'AGENTS.md'
    assert target.exists()
    assert '## xyb' in target.read_text(encoding='utf-8')


def test_uninstall_local_removes_agents_section(tmp_path) -> None:
    install_local(tmp_path)
    msg = uninstall_local(tmp_path)
    assert 'AGENTS.md' in msg


def test_install_claude_local_writes_claude_md(tmp_path) -> None:
    msg = install_claude_local(tmp_path)
    assert 'CLAUDE.md' in msg
    target = tmp_path / 'CLAUDE.md'
    assert target.exists()
    assert '## xyb' in target.read_text(encoding='utf-8')


def test_install_codex_local_writes_agents_md(tmp_path) -> None:
    msg = install_codex_local(tmp_path)
    assert 'AGENTS.md' in msg
    target = tmp_path / 'AGENTS.md'
    assert target.exists()
    assert '## xyb' in target.read_text(encoding='utf-8')


def test_uninstall_platform_local_sections(tmp_path) -> None:
    install_claude_local(tmp_path)
    install_codex_local(tmp_path)
    assert 'CLAUDE.md' in uninstall_claude_local(tmp_path)
    assert 'AGENTS.md' in uninstall_codex_local(tmp_path)


def test_install_other_platform_locals_write_expected_files(tmp_path) -> None:
    assert 'OPENCODE.md' in install_opencode_local(tmp_path)
    assert 'CURSOR.md' in install_cursor_local(tmp_path)
    assert 'GEMINI.md' in install_gemini_local(tmp_path)
    assert (tmp_path / 'OPENCODE.md').exists()
    assert (tmp_path / 'CURSOR.md').exists()
    assert (tmp_path / 'GEMINI.md').exists()


def test_uninstall_other_platform_locals(tmp_path) -> None:
    install_opencode_local(tmp_path)
    install_cursor_local(tmp_path)
    install_gemini_local(tmp_path)
    assert 'OPENCODE.md' in uninstall_opencode_local(tmp_path)
    assert 'CURSOR.md' in uninstall_cursor_local(tmp_path)
    assert 'GEMINI.md' in uninstall_gemini_local(tmp_path)


def test_install_global_platform_writes_global_files(tmp_path) -> None:
    msg = install_global_platform('codex', home_dir=tmp_path)
    assert '.codex/AGENTS.md' in msg
    config_path = tmp_path / '.codex' / 'AGENTS.md'
    assert config_path.exists()
    assert 'xyb hook install' in config_path.read_text(encoding='utf-8')
    skill = tmp_path / '.xyb' / 'skills' / 'xyb-global-skill.json'
    assert skill.exists()


def test_uninstall_global_platform_removes_global_files(tmp_path) -> None:
    install_global_platform('claude', home_dir=tmp_path)
    msg = uninstall_global_platform('claude', home_dir=tmp_path)
    assert '.claude/CLAUDE.md' in msg
