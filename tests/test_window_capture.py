import os
import types

import pytest

from copilot import app


class FakeWidget:
    def winId(self):
        return 1234


def test_windows_path_asks_for_exclusion_from_capture(monkeypatch):
    calls = []
    monkeypatch.setattr(app, "_set_display_affinity", lambda hwnd, flag: calls.append((hwnd, flag)) or True)
    assert app._configure_windows(FakeWidget(), hide_from_capture=True) is True
    assert calls == [(1234, app.WDA_EXCLUDEFROMCAPTURE)]


def test_windows_path_can_switch_the_hiding_off_for_testing(monkeypatch):
    calls = []
    monkeypatch.setattr(app, "_set_display_affinity", lambda hwnd, flag: calls.append((hwnd, flag)) or True)
    assert app._configure_windows(FakeWidget(), hide_from_capture=False) is False
    assert calls == [(1234, app.WDA_NONE)]


def test_windows_path_says_not_hidden_when_windows_refuses(monkeypatch):
    monkeypatch.setattr(app, "_set_display_affinity", lambda hwnd, flag: False)
    assert app._configure_windows(FakeWidget(), hide_from_capture=True) is False


def test_windows_path_never_raises(monkeypatch):
    def boom(hwnd, flag):
        raise OSError("no user32 here")

    monkeypatch.setattr(app, "_set_display_affinity", boom)
    assert app._configure_windows(FakeWidget(), hide_from_capture=True) is False


@pytest.mark.parametrize("platform, expected", [("win32", "windows"), ("darwin", "macos"), ("linux", "macos")])
def test_platform_choice(monkeypatch, platform, expected):
    monkeypatch.setattr(app, "sys", types.SimpleNamespace(platform=platform))
    monkeypatch.setattr(app, "_configure_windows", lambda widget, hide: "windows")
    monkeypatch.setattr(app, "_configure_macos", lambda widget, hide: "macos")
    assert app.configure_native_window(FakeWidget(), True) == expected


@pytest.mark.skipif(os.name != "nt", reason="calls the real Windows function")
def test_real_call_with_a_bad_handle_returns_false_and_does_not_raise():
    assert app._set_display_affinity(0, app.WDA_EXCLUDEFROMCAPTURE) is False
