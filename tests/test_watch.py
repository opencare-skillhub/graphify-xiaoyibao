from __future__ import annotations

from xyb.watch import _observer_mode, _notify_only


def test_observer_mode_defaults_to_auto(monkeypatch) -> None:
    monkeypatch.delenv('XYB_WATCH_OBSERVER', raising=False)
    assert _observer_mode() == 'auto'


def test_observer_mode_invalid_falls_back_to_auto(monkeypatch) -> None:
    monkeypatch.setenv('XYB_WATCH_OBSERVER', 'banana')
    assert _observer_mode() == 'auto'


def test_notify_only_creates_flag(tmp_path) -> None:
    _notify_only(tmp_path)
    flag = tmp_path / 'graphify-out' / 'needs_update'
    assert flag.exists()
    assert flag.read_text() == '1'
