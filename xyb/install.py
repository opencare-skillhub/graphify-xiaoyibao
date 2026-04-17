from __future__ import annotations

from pathlib import Path
import json

_AGENTS_SECTION = """\
## xyb

This project has an xyb knowledge graph in `graphify-out/`.

Rules:
- Before answering architecture or corpus questions, read `graphify-out/GRAPH_REPORT.md`
- Prefer `graphify-out/graph.json` / `xyb query` over searching raw files blindly
- After major content changes, run `xyb analyze . --output-dir graphify-out`
"""

_AGENTS_MARKER = "## xyb"
_CLAUDE_SECTION = """\
## xyb

This project has an xyb knowledge graph in `graphify-out/`.

Rules:
- Before answering architecture or corpus questions, read `graphify-out/GRAPH_REPORT.md`
- If `graphify-out/wiki/index.md` exists, navigate it before reading raw files
- After major content changes, run `xyb analyze . --output-dir graphify-out`
"""
_CLAUDE_MARKER = "## xyb"
_PLATFORM_SECTION_TEMPLATE = """\
## xyb

This project has an xyb knowledge graph in `graphify-out/`.

Rules:
- Before answering repository or corpus questions, read `graphify-out/GRAPH_REPORT.md`
- If `graphify-out/wiki/index.md` exists, use the wiki as the primary navigation surface
- Prefer `xyb query`, `xyb path`, and `xyb explain` over blind file search
- After major content changes, run `xyb analyze . --output-dir graphify-out`
- If this repository uses git, install automation with `xyb hook install`
"""
_GLOBAL_XYB_SECTION = """\
## xyb (global)

Global xyb integration is enabled.

Rules:
- Prefer graph-first navigation (`xyb query`, `xyb path`, `xyb explain`)
- For repository-level automation, run `xyb hook install` inside that repo
"""
_GLOBAL_MARKER = "## xyb (global)"

_GLOBAL_CONFIG_PATHS = {
    "claude": ".claude/CLAUDE.md",
    "codex": ".codex/AGENTS.md",
    "opencode": ".opencode/AGENTS.md",
    "cursor": ".cursor/AGENTS.md",
    "gemini": ".gemini/AGENTS.md",
}


def install_local(project_dir: Path = Path(".")) -> str:
    target = project_dir / "AGENTS.md"
    if target.exists():
        content = target.read_text(encoding="utf-8")
        if _AGENTS_MARKER in content:
            return f"xyb already configured in {target}"
        target.write_text(content.rstrip() + "\n\n" + _AGENTS_SECTION, encoding="utf-8")
        return f"xyb section appended to {target}"
    target.write_text(_AGENTS_SECTION, encoding="utf-8")
    return f"xyb section written to {target}"


def uninstall_local(project_dir: Path = Path(".")) -> str:
    target = project_dir / "AGENTS.md"
    if not target.exists():
        return f"{target} not found - nothing to remove."
    content = target.read_text(encoding="utf-8")
    if _AGENTS_MARKER not in content:
        return f"xyb section not found in {target}."
    parts = content.split(_AGENTS_MARKER, 1)
    kept = parts[0].rstrip()
    if kept:
        target.write_text(kept + "\n", encoding="utf-8")
        return f"xyb section removed from {target}"
    target.unlink()
    return f"removed {target}"


def install_claude_local(project_dir: Path = Path(".")) -> str:
    target = project_dir / "CLAUDE.md"
    if target.exists():
        content = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER in content:
            return f"xyb already configured in {target}"
        target.write_text(content.rstrip() + "\n\n" + _CLAUDE_SECTION, encoding="utf-8")
        return f"xyb section appended to {target}"
    target.write_text(_CLAUDE_SECTION, encoding="utf-8")
    return f"xyb section written to {target}"


def uninstall_claude_local(project_dir: Path = Path(".")) -> str:
    target = project_dir / "CLAUDE.md"
    if not target.exists():
        return f"{target} not found - nothing to remove."
    content = target.read_text(encoding="utf-8")
    if _CLAUDE_MARKER not in content:
        return f"xyb section not found in {target}."
    parts = content.split(_CLAUDE_MARKER, 1)
    kept = parts[0].rstrip()
    if kept:
        target.write_text(kept + "\n", encoding="utf-8")
        return f"xyb section removed from {target}"
    target.unlink()
    return f"removed {target}"


def install_codex_local(project_dir: Path = Path(".")) -> str:
    return install_local(project_dir)


def uninstall_codex_local(project_dir: Path = Path(".")) -> str:
    return uninstall_local(project_dir)


def _install_platform_file(project_dir: Path, filename: str) -> str:
    target = project_dir / filename
    if target.exists():
        content = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER in content:
            return f"xyb already configured in {target}"
        target.write_text(content.rstrip() + "\n\n" + _PLATFORM_SECTION_TEMPLATE, encoding="utf-8")
        return f"xyb section appended to {target}"
    target.write_text(_PLATFORM_SECTION_TEMPLATE, encoding="utf-8")
    return f"xyb section written to {target}"


def _uninstall_platform_file(project_dir: Path, filename: str) -> str:
    target = project_dir / filename
    if not target.exists():
        return f"{target} not found - nothing to remove."
    content = target.read_text(encoding="utf-8")
    if _CLAUDE_MARKER not in content:
        return f"xyb section not found in {target}."
    parts = content.split(_CLAUDE_MARKER, 1)
    kept = parts[0].rstrip()
    if kept:
        target.write_text(kept + "\n", encoding="utf-8")
        return f"xyb section removed from {target}"
    target.unlink()
    return f"removed {target}"


def install_opencode_local(project_dir: Path = Path(".")) -> str:
    return _install_platform_file(project_dir, "OPENCODE.md")


def uninstall_opencode_local(project_dir: Path = Path(".")) -> str:
    return _uninstall_platform_file(project_dir, "OPENCODE.md")


def install_cursor_local(project_dir: Path = Path(".")) -> str:
    return _install_platform_file(project_dir, "CURSOR.md")


def uninstall_cursor_local(project_dir: Path = Path(".")) -> str:
    return _uninstall_platform_file(project_dir, "CURSOR.md")


def install_gemini_local(project_dir: Path = Path(".")) -> str:
    return _install_platform_file(project_dir, "GEMINI.md")


def uninstall_gemini_local(project_dir: Path = Path(".")) -> str:
    return _uninstall_platform_file(project_dir, "GEMINI.md")


def _append_or_create_section(target: Path, marker: str, section: str) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        content = target.read_text(encoding="utf-8")
        if marker in content:
            return f"xyb already configured in {target}"
        target.write_text(content.rstrip() + "\n\n" + section, encoding="utf-8")
        return f"xyb section appended to {target}"
    target.write_text(section, encoding="utf-8")
    return f"xyb section written to {target}"


def _remove_section(target: Path, marker: str) -> str:
    if not target.exists():
        return f"{target} not found - nothing to remove."
    content = target.read_text(encoding="utf-8")
    if marker not in content:
        return f"xyb section not found in {target}."
    parts = content.split(marker, 1)
    kept = parts[0].rstrip()
    if kept:
        target.write_text(kept + "\n", encoding="utf-8")
        return f"xyb section removed from {target}"
    target.unlink()
    return f"removed {target}"


def _write_global_skill_manifest(home_dir: Path) -> Path:
    target = home_dir / ".xyb" / "skills" / "xyb-global-skill.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": "xyb-global-skill",
        "commands": ["xyb analyze", "xyb query", "xyb path", "xyb explain", "xyb hook install"],
        "scope": "global-skeleton",
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def install_global_platform(platform: str, home_dir: Path = Path.home()) -> str:
    key = platform.strip().lower()
    if key not in _GLOBAL_CONFIG_PATHS:
        raise ValueError(f"Unsupported platform: {platform}")
    config_path = home_dir / _GLOBAL_CONFIG_PATHS[key]
    config_msg = _append_or_create_section(config_path, _GLOBAL_MARKER, _GLOBAL_XYB_SECTION)
    skill_path = _write_global_skill_manifest(home_dir)
    return f"{config_msg}\nglobal skill manifest: {skill_path}"


def uninstall_global_platform(platform: str, home_dir: Path = Path.home()) -> str:
    key = platform.strip().lower()
    if key not in _GLOBAL_CONFIG_PATHS:
        raise ValueError(f"Unsupported platform: {platform}")
    config_path = home_dir / _GLOBAL_CONFIG_PATHS[key]
    config_msg = _remove_section(config_path, _GLOBAL_MARKER)
    skill_path = home_dir / ".xyb" / "skills" / "xyb-global-skill.json"
    if skill_path.exists():
        skill_path.unlink()
        skill_msg = f"removed {skill_path}"
    else:
        skill_msg = f"{skill_path} not found - nothing to remove."
    return f"{config_msg}\n{skill_msg}"
