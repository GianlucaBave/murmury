"""Tests for the audio source interface in copilot/audio.py and copilot/listen.py."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from copilot.audio import FRAME, SAMPLE_RATE, open_source
from copilot.listen import StreamingTranscriber, Utterance, listen


def sine(frames: int, amplitude: float = 0.2) -> np.ndarray:
    """`frames` 30 ms frames of a 440 Hz sine wave."""
    t = np.arange(frames * FRAME, dtype=np.float64) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


def silence(frames: int) -> np.ndarray:
    return np.zeros(frames * FRAME, dtype=np.float32)


def test_listen_with_fake_source_yields_utterances(monkeypatch):
    """Verify listen() ingests chunks from a fake audio source and yields utterances."""
    speech_chunks = [sine(33), silence(30)]

    @contextmanager
    def fake_open_source(name: str = "system", chunk_frames: int = 3):
        def stream():
            for chunk in speech_chunks:
                yield chunk
        yield stream()

    # Isolate from ML hardware / models
    monkeypatch.setattr("copilot.listen.warm_up", lambda: None)
    monkeypatch.setattr("copilot.listen.transcribe", lambda audio, vocabulary="": "test transcript")
    monkeypatch.setattr("copilot.listen.open_source", fake_open_source)

    utterances = list(listen("system"))
    assert len(utterances) == 1
    u = utterances[0]
    assert isinstance(u, Utterance)
    assert u.speaker == "them"
    assert u.text == "test transcript"
    assert u.seconds == pytest.approx((33 * FRAME) / SAMPLE_RATE, rel=1e-2)
    assert u.latency >= 0

    # For mic source, speaker must be "me"
    utterances_mic = list(listen("mic"))
    assert len(utterances_mic) == 1
    assert utterances_mic[0].speaker == "me"


def test_open_source_stops_helper_on_normal_exit():
    """Helper subprocess must be terminated when the caller exits the context."""
    mock_proc = MagicMock()
    mock_proc.stdout.read.side_effect = [b"\x00" * (FRAME * 4 * 3), b""]
    mock_proc.poll.return_value = None

    with patch("copilot.audio.subprocess.Popen", return_value=mock_proc):
        with open_source("system") as stream:
            chunks = list(stream)
            assert len(chunks) == 1

        mock_proc.terminate.assert_called_once()


def test_open_source_stops_helper_on_early_break():
    """Helper subprocess must be terminated even if caller stops reading early."""
    mock_proc = MagicMock()
    mock_proc.stdout.read.return_value = b"\x00" * (FRAME * 4 * 3)
    mock_proc.poll.return_value = None

    with patch("copilot.audio.subprocess.Popen", return_value=mock_proc):
        with open_source("system") as stream:
            for _ in stream:
                break  # stop early

        mock_proc.terminate.assert_called_once()


def test_open_source_stops_helper_on_exception():
    """Helper subprocess must be terminated if an exception is raised inside context block."""
    mock_proc = MagicMock()
    mock_proc.stdout.read.return_value = b"\x00" * (FRAME * 4 * 3)
    mock_proc.poll.return_value = None

    with patch("copilot.audio.subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="caller error"):
            with open_source("system") as stream:
                for _ in stream:
                    raise RuntimeError("caller error")

        mock_proc.terminate.assert_called_once()


def test_listen_and_run_do_not_call_popen_directly():
    """Ensure listen() and StreamingTranscriber._run() in copilot.listen do not use subprocess.Popen."""
    import inspect
    import copilot.listen

    source = inspect.getsource(copilot.listen)
    assert "subprocess.Popen" not in source, "copilot.listen should not call subprocess.Popen directly"


def test_streaming_transcriber_run_uses_open_source(monkeypatch):
    """Ensure StreamingTranscriber._run() consumes from open_source."""
    speech_chunks = [sine(33), silence(30)]

    @contextmanager
    def fake_open_source(name: str = "system", chunk_frames: int = 3):
        def stream():
            for chunk in speech_chunks:
                yield chunk
        yield stream()

    ready_called = []
    transcriber = StreamingTranscriber("system", min_seconds=0.6)

    monkeypatch.setattr("copilot.listen.open_source", fake_open_source)
    monkeypatch.setattr(transcriber.pool, "submit", lambda fn, *args: MagicMock(
        done=lambda: True,
        result=lambda: "streaming transcript"
    ))

    events = list(transcriber._run(on_ready=lambda: ready_called.append(True)))
    assert ready_called == [True]
    assert any(e.text == "streaming transcript" for e in events)

