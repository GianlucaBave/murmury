import os
import subprocess
import sys

import pytest

from copilot.app import keep_awake


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
