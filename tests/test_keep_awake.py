import subprocess
import sys
from unittest.mock import MagicMock

import pytest

# Mock all submodules copilot.app imports so only keep_awake() is tested
for _mod in (
    "copilot.material",
    "copilot.providers",
    "copilot.answer",
    "copilot.openai_copilot",
    "copilot.listen",
    "copilot.theme",
    "copilot.chrome",
    "copilot.pipeline",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
):
    sys.modules[_mod] = MagicMock()

from copilot.app import keep_awake


class FakePopen:
    def __init__(self, args):
        self.args = args


def test_keep_awake_starts_caffeinate_on_darwin(monkeypatch):
    started = []

    def fake_popen(args):
        started.append(args)

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    import os

    monkeypatch.setattr(os, "getpid", lambda: 1234)
    keep_awake()
    assert started == [["caffeinate", "-di", "-w", "1234"]]


def test_keep_awake_does_nothing_on_windows(monkeypatch):
    started = []

    def fake_popen(args):
        started.append(args)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    keep_awake()
    assert started == []


def test_keep_awake_does_nothing_on_linux(monkeypatch):
    started = []

    def fake_popen(args):
        started.append(args)

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    keep_awake()
    assert started == []
