from __future__ import annotations

import re
from pathlib import Path

_HOOK_MARKER = "# xyb-hook-start"
_HOOK_MARKER_END = "# xyb-hook-end"
_CHECKOUT_MARKER = "# xyb-checkout-hook-start"
_CHECKOUT_MARKER_END = "# xyb-checkout-hook-end"

_HOOK_SCRIPT = """\
# xyb-hook-start
# Auto-rebuilds the xyb graph after each commit.
# Installed by: xyb hook install
if command -v xyb >/dev/null 2>&1; then
  xyb analyze . --output-dir graphify-out >/dev/null 2>&1 || true
fi
# xyb-hook-end
"""

_CHECKOUT_SCRIPT = """\
# xyb-checkout-hook-start
# Auto-rebuilds the xyb graph on branch switch.
# Installed by: xyb hook install
BRANCH_SWITCH=$3
if [ "$BRANCH_SWITCH" = "1" ] && command -v xyb >/dev/null 2>&1; then
  xyb analyze . --output-dir graphify-out >/dev/null 2>&1 || true
fi
# xyb-checkout-hook-end
"""


def _git_root(path: Path) -> Path | None:
    current = path.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _install_hook(hooks_dir: Path, name: str, script: str, marker: str) -> str:
    hook_path = hooks_dir / name
    if hook_path.exists():
        content = hook_path.read_text(encoding="utf-8")
        if marker in content:
            return f"already installed at {hook_path}"
        hook_path.write_text(content.rstrip() + "\n\n" + script, encoding="utf-8", newline="\n")
        return f"appended to existing {name} hook at {hook_path}"
    hook_path.write_text("#!/bin/sh\n" + script, encoding="utf-8", newline="\n")
    hook_path.chmod(0o755)
    return f"installed at {hook_path}"


def _uninstall_hook(hooks_dir: Path, name: str, marker: str, marker_end: str) -> str:
    hook_path = hooks_dir / name
    if not hook_path.exists():
        return f"no {name} hook found - nothing to remove."
    content = hook_path.read_text(encoding="utf-8")
    if marker not in content:
        return f"xyb hook not found in {name} - nothing to remove."
    new_content = re.sub(
        rf"{re.escape(marker)}.*?{re.escape(marker_end)}\n?",
        "",
        content,
        flags=re.DOTALL,
    ).strip()
    if not new_content or new_content in ("#!/bin/bash", "#!/bin/sh"):
        hook_path.unlink()
        return f"removed {name} hook at {hook_path}"
    hook_path.write_text(new_content + "\n", encoding="utf-8", newline="\n")
    return f"xyb removed from {name} at {hook_path} (other hook content preserved)"


def install(path: Path = Path(".")) -> str:
    root = _git_root(path)
    if root is None:
        raise RuntimeError(f"No git repository found at or above {path.resolve()}")
    hooks_dir = root / ".git" / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    commit_msg = _install_hook(hooks_dir, "post-commit", _HOOK_SCRIPT, _HOOK_MARKER)
    checkout_msg = _install_hook(hooks_dir, "post-checkout", _CHECKOUT_SCRIPT, _CHECKOUT_MARKER)
    return f"post-commit: {commit_msg}\npost-checkout: {checkout_msg}"


def uninstall(path: Path = Path(".")) -> str:
    root = _git_root(path)
    if root is None:
        raise RuntimeError(f"No git repository found at or above {path.resolve()}")
    hooks_dir = root / ".git" / "hooks"
    commit_msg = _uninstall_hook(hooks_dir, "post-commit", _HOOK_MARKER, _HOOK_MARKER_END)
    checkout_msg = _uninstall_hook(hooks_dir, "post-checkout", _CHECKOUT_MARKER, _CHECKOUT_MARKER_END)
    return f"post-commit: {commit_msg}\npost-checkout: {checkout_msg}"


def status(path: Path = Path(".")) -> str:
    root = _git_root(path)
    if root is None:
        return "Not in a git repository."
    hooks_dir = root / ".git" / "hooks"

    def _check(name: str, marker: str) -> str:
        p = hooks_dir / name
        if not p.exists():
            return "not installed"
        return "installed" if marker in p.read_text(encoding="utf-8") else "not installed (hook exists but xyb not found)"

    commit = _check("post-commit", _HOOK_MARKER)
    checkout = _check("post-checkout", _CHECKOUT_MARKER)
    return f"post-commit: {commit}\npost-checkout: {checkout}"
