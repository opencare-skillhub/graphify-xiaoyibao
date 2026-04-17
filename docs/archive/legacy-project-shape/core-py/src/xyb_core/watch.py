from __future__ import annotations

import os
import platform
from pathlib import Path

VALID_MODES = {"auto", "native", "polling"}


def _observer_mode() -> str:
    mode = os.environ.get("XYB_WATCH_OBSERVER", "auto").strip().lower()
    return mode if mode in VALID_MODES else "auto"


def choose_observer_kind() -> str:
    mode = _observer_mode()
    if mode == "polling":
        return "polling"
    if mode == "native":
        return "native"
    return "polling" if platform.system() == "Darwin" else "native"


def build_update_message(output_path: Path) -> str:
    return f"[xyb] 病情报告已更新 → {output_path}"
