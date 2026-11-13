"""Tests for StreamingTranscriber in copilot/listen.py: partial transcripts and the fast final.

No microphone, no audiotap helper and no mlx: subprocess.Popen is replaced by a fake whose stdout
is a BytesIO of float32 samples, transcribe() by a function that reports the audio length, and the
worker pool by an executor that runs each job at once, so event order is deterministic and nothing sleeps.

Audio is built in whole 30 ms frames (FRAME samples): loud frames are speech, zeros are silence.
Defaults under test: partial_every 0.6 s (20 frames), fast_margin 0.2 s, min_seconds 0.6 s (20 frames),
silence_ms 400 (13 quiet frames end an utterance). The reader takes 3 frames (~90 ms) per read.
"""

import io
import time
from concurrent.futures import Future

import numpy as np
import pytest

from copilot import listen
from copilot.listen import FRAME, SAMPLE_RATE, StreamingTranscriber

SILENCE_FRAMES = 30  # comfortably more than the 13 quiet frames that end an utterance


def loud(frames: int) -> np.ndarray:
    return np.full(frames * FRAME, 0.1, dtype=np.float32)  # RMS 0.1, far above the 0.008 threshold


def quiet(frames: int) -> np.ndarray:
    return np.zeros(frames * FRAME, dtype=np.float32)


class FakeTap:
    """Stands in for the audiotap process: stdout is the audio, terminate() is recorded."""

    def __init__(self, audio: np.ndarray):
        self.stdout = io.BytesIO(audio.astype(np.float32).tobytes())
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


class InlinePool:
    """Runs every job as soon as it is submitted and hands back a finished Future."""

    def submit(self, fn, *args, **kwargs) -> Future:
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as error:  # pragma: no cover - mirrors a real executor
            future.set_exception(error)
        return future


class Rig:
    """One transcriber wired to fakes; `lengths` holds the sample count of every transcribe() call."""

    def __init__(self, monkeypatch, audio: np.ndarray, **options):
        self.tap = FakeTap(audio)
        self.popen_args: list = []
        self.lengths: list[int] = []

        def fake_popen(args, **kwargs):
            self.popen_args.append(args)
            return self.tap

        def fake_transcribe(samples, vocabulary=""):
            self.lengths.append(len(samples))
            return f"len={len(samples)}"

        monkeypatch.setattr(listen.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(listen, "transcribe", fake_transcribe)
        self.transcriber = StreamingTranscriber(**options)
        self.transcriber.pool = InlinePool()

    def events(self) -> list[listen.Event]:
        return list(self.transcriber._run())


def covered(event: listen.Event) -> int:
    """Samples of audio an event's text came from (the fake transcribe writes `len=<samples>`)."""
    return int(event.text.removeprefix("len="))


def test_long_utterance_gives_partials_about_every_partial_every_then_one_final(monkeypatch):
    rig = Rig(monkeypatch, np.concatenate([loud(100), quiet(SILENCE_FRAMES)]))
    events = rig.events()

    partials = [e for e in events if e.kind == "partial"]
    finals = [e for e in events if e.kind == "final"]
    assert len(finals) == 1
    assert events[-1] is finals[0]  # the final comes last, once
    assert len(partials) >= 3

    every = rig.transcriber.partial_every
    sizes = [covered(p) for p in partials]
    assert sizes[0] >= every  # the first partial waits for partial_every of speech
    for earlier, later in zip(sizes, sizes[1:]):
        # a partial is due once another partial_every has gathered; reads are 3 frames, so at most that late
        assert every <= later - earlier < every + 3 * FRAME
    assert covered(finals[0]) == 100 * FRAME  # the final covers all the speech, not the silence after it


def test_final_is_fast_when_the_last_partial_covers_all_but_fast_margin(monkeypatch):
    # 21 frames: one partial (21 frames) is taken, then silence ends the utterance with nothing missing
    rig = Rig(monkeypatch, np.concatenate([loud(21), quiet(SILENCE_FRAMES)]))
    events = rig.events()

    assert [e.kind for e in events] == ["partial", "final"]
    final = events[-1]
    assert final.fast is True
    assert final.text == events[0].text == f"len={21 * FRAME}"
    assert rig.lengths == [21 * FRAME]  # no second transcription for the final


def test_final_is_a_fresh_transcription_when_the_last_partial_falls_short(monkeypatch):
    # 30 frames: the only partial covers 21 frames, so 9 frames (270 ms) are missing: more than 0.2 s
    rig = Rig(monkeypatch, np.concatenate([loud(30), quiet(SILENCE_FRAMES)]))
    events = rig.events()

    assert [e.kind for e in events] == ["partial", "final"]
    final = events[-1]
    assert final.fast is False
    assert final.text == f"len={30 * FRAME}"  # the whole utterance, not the partial's text
    assert rig.lengths == [21 * FRAME, 30 * FRAME]


@pytest.mark.parametrize("margin_frames, fast", [(10, True), (9, True), (8, False), (7, False)])
def test_fast_margin_boundary(monkeypatch, margin_frames, fast):
    """The partial covers 21 of 30 frames, so 9 frames are missing: fast up to a margin of 9 frames."""
    rig = Rig(monkeypatch, np.concatenate([loud(30), quiet(SILENCE_FRAMES)]))
    rig.transcriber.fast_margin = margin_frames * FRAME  # set in samples, so no float rounding in the edge

    final = rig.events()[-1]
    assert final.kind == "final"
    assert final.fast is fast
    assert final.text == (f"len={21 * FRAME}" if fast else f"len={30 * FRAME}")
    assert len(rig.lengths) == (1 if fast else 2)


def test_speech_shorter_than_min_seconds_gives_no_event(monkeypatch):
    rig = Rig(monkeypatch, np.concatenate([loud(19), quiet(SILENCE_FRAMES)]))  # 570 ms < 600 ms

    assert rig.events() == []
    assert rig.lengths == []  # not even transcribed


def test_speech_of_exactly_min_seconds_is_kept(monkeypatch):
    rig = Rig(monkeypatch, np.concatenate([loud(20), quiet(SILENCE_FRAMES)]))  # 600 ms

    events = rig.events()
    assert [e.kind for e in events][-1] == "final"
    assert covered(events[-1]) == 20 * FRAME


def test_two_utterances_each_get_their_own_final(monkeypatch):
    audio = np.concatenate([loud(30), quiet(SILENCE_FRAMES), loud(21), quiet(SILENCE_FRAMES)])
    rig = Rig(monkeypatch, audio)
    events = rig.events()

    finals = [e for e in events if e.kind == "final"]
    assert [covered(f) for f in finals] == [30 * FRAME, 21 * FRAME]
    assert finals[0].started < finals[1].started


@pytest.mark.parametrize("source, speaker", [("system", "them"), ("mic", "me")])
def test_speaker_follows_the_source_and_started_is_set(monkeypatch, source, speaker):
    rig = Rig(monkeypatch, np.concatenate([loud(30), quiet(SILENCE_FRAMES)]), source=source)
    before = time.perf_counter()
    events = rig.events()
    after = time.perf_counter()

    assert events
    assert rig.popen_args == [[str(listen.AUDIOTAP), source]]
    for event in events:
        assert event.speaker == speaker
        assert before <= event.started <= event.at <= after
    assert len({e.started for e in events}) == 1  # one utterance, one start time


def test_helper_is_terminated_when_the_audio_ends(monkeypatch):
    rig = Rig(monkeypatch, np.concatenate([loud(30), quiet(SILENCE_FRAMES)]))
    assert not rig.tap.terminated

    rig.events()  # reads until the fake stdout is empty

    assert rig.tap.terminated


def test_helper_is_terminated_when_the_caller_stops_listening(monkeypatch):
    rig = Rig(monkeypatch, np.concatenate([loud(100), quiet(SILENCE_FRAMES)]))
    stream = rig.transcriber._run()

    assert next(stream).kind == "partial"
    assert not rig.tap.terminated  # still reading
    stream.close()  # the caller stops iterating

    assert rig.tap.terminated


def test_on_ready_is_called_once_the_helper_has_started(monkeypatch):
    rig = Rig(monkeypatch, quiet(SILENCE_FRAMES))
    calls = []

    list(rig.transcriber._run(on_ready=lambda: calls.append(len(rig.popen_args))))

    assert calls == [1]
