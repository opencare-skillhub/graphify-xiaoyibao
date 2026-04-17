from __future__ import annotations

from xyb_core.watch import _observer_mode, build_update_message, choose_observer_kind


def test_observer_mode_defaults_to_auto(monkeypatch) -> None:
    monkeypatch.delenv("XYB_WATCH_OBSERVER", raising=False)
    assert _observer_mode() == "auto"


def test_observer_mode_invalid_falls_back_to_auto(monkeypatch) -> None:
    monkeypatch.setenv("XYB_WATCH_OBSERVER", "banana")
    assert _observer_mode() == "auto"


def test_observer_mode_accepts_native(monkeypatch) -> None:
    monkeypatch.setenv("XYB_WATCH_OBSERVER", "native")
    assert _observer_mode() == "native"


def test_observer_mode_accepts_polling(monkeypatch) -> None:
    monkeypatch.setenv("XYB_WATCH_OBSERVER", "polling")
    assert _observer_mode() == "polling"


def test_choose_observer_kind_uses_polling_on_darwin(monkeypatch) -> None:
    monkeypatch.delenv("XYB_WATCH_OBSERVER", raising=False)
    monkeypatch.setattr("xyb_core.watch.platform.system", lambda: "Darwin")
    assert choose_observer_kind() == "polling"


def test_choose_observer_kind_respects_native_override(monkeypatch) -> None:
    monkeypatch.setenv("XYB_WATCH_OBSERVER", "native")
    monkeypatch.setattr("xyb_core.watch.platform.system", lambda: "Darwin")
    assert choose_observer_kind() == "native"


def test_build_update_message_contains_target(tmp_path) -> None:
    target = tmp_path / "xyb-out" / "report.md"
    message = build_update_message(target)
    assert str(target) in message
