"""Tests for the speech-to-text backend choice in copilot/stt.py.

Both libraries are replaced by fakes, so no model is loaded or downloaded and nothing touches the network.
On each platform the other platform's library is made unimportable, so a stray import fails the test.
"""

import sys
import types

import numpy as np
import pytest

from copilot import listen, stt

AUDIO = np.zeros(16_000, dtype=np.float32)


class Segment:
    def __init__(self, text):
        self.text = text


def fake_mlx(calls):
    module = types.ModuleType("mlx_whisper")

    def transcribe(audio, **options):
        calls.append(options)
        return {"text": " mlx text "}

    module.transcribe = transcribe
    return module


def fake_faster_whisper(loads, calls):
    class WhisperModel:
        def __init__(self, size, **options):
            loads.append((size, options))

        def transcribe(self, audio, **options):
            calls.append(options)
            return (segment for segment in [Segment(" faster"), Segment(" whisper ")]), None

    module = types.ModuleType("faster_whisper")
    module.WhisperModel = WhisperModel
    return module


@pytest.fixture
def backends(monkeypatch):
    seen = types.SimpleNamespace(mlx=[], loads=[], faster=[])
    monkeypatch.setattr(stt, "_model", None)
    # a stand-in already in place, so mlx's word-timing stub is not installed for the rest of the run
    monkeypatch.setitem(sys.modules, "mlx_whisper.timing", types.ModuleType("mlx_whisper.timing"))

    def on(platform):
        monkeypatch.setattr(sys, "platform", platform)
        mac = platform == "darwin"
        monkeypatch.setitem(sys.modules, "mlx_whisper", fake_mlx(seen.mlx) if mac else None)
        monkeypatch.setitem(sys.modules, "faster_whisper", None if mac else fake_faster_whisper(seen.loads, seen.faster))

    seen.on = on
    return seen


def test_macos_uses_mlx_whisper_and_never_imports_faster_whisper(backends):
    backends.on("darwin")
    assert stt.transcribe(AUDIO, "Murmury, Kubernetes") == "mlx text"
    assert backends.mlx == [{"path_or_hf_repo": stt.MLX_MODEL, "condition_on_previous_text": False,
                             "initial_prompt": "Murmury, Kubernetes"}]
    assert backends.loads == []


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_other_platforms_use_faster_whisper_and_never_import_mlx(backends, platform):
    backends.on(platform)
    assert stt.transcribe(AUDIO, "Murmury, Kubernetes") == "faster whisper"
    assert backends.faster == [{"initial_prompt": "Murmury, Kubernetes", "condition_on_previous_text": False}]
    assert backends.mlx == []


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
def test_no_vocabulary_means_no_initial_prompt(backends, platform):
    backends.on(platform)
    stt.transcribe(AUDIO)
    assert (backends.mlx or backends.faster)[0]["initial_prompt"] is None


def test_faster_whisper_model_is_loaded_once_on_cpu(backends):
    backends.on("linux")
    stt.transcribe(AUDIO)
    stt.transcribe(AUDIO)
    assert backends.loads == [("small", {"device": "cpu", "compute_type": "int8"})]


def test_listen_uses_the_same_transcribe():
    assert listen.transcribe is stt.transcribe
