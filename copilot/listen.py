"""Live listening: audio from the audiotap helper, cut into utterances, transcribed on this Mac.

An utterance ends after a short silence; each finished utterance is transcribed with the local
Whisper model and yielded with who spoke ("them" for the Mac's audio output, "me" for the mic).
Nothing is written to disk.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .stt import transcribe

SAMPLE_RATE = 16_000
FRAME = 480  # 30 ms
# inside the packaged app the helper sits in the bundle's resources; from source, next to the code
_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
AUDIOTAP = _ROOT / "audiotap" / ("audiotap.exe" if sys.platform == "win32" else "audiotap")

@dataclass(frozen=True)
class Utterance:
    speaker: str  # "them" or "me"
    text: str
    seconds: float  # length of the speech
    latency: float  # from end of speech to text ready


class Segmenter:
    """Energy-based cut: speech starts above `threshold`, ends after `silence_ms` below it."""

    def __init__(self, threshold: float = 0.008, silence_ms: int = 700, max_seconds: float = 20.0,
                 min_seconds: float = 0.6):
        self.threshold = threshold
        self.silence_frames = silence_ms // 30
        self.max_frames = int(max_seconds * 1000 / 30)
        self.min_frames = int(min_seconds * 1000 / 30)
        self.frames: list[np.ndarray] = []
        self.quiet = 0
        self.pending = np.zeros(0, dtype=np.float32)

    def feed(self, samples: np.ndarray) -> Iterator[np.ndarray]:
        self.pending = np.concatenate([self.pending, samples])
        while len(self.pending) >= FRAME:
            frame, self.pending = self.pending[:FRAME], self.pending[FRAME:]
            loud = float(np.sqrt(np.mean(frame * frame))) > self.threshold
            if self.frames or loud:
                self.frames.append(frame)
                self.quiet = 0 if loud else self.quiet + 1
            if self.frames and (self.quiet >= self.silence_frames or len(self.frames) >= self.max_frames):
                speech = self.frames[: len(self.frames) - self.quiet] if self.quiet else self.frames
                self.frames, self.quiet = [], 0
                if len(speech) >= self.min_frames:
                    yield np.concatenate(speech)


def warm_up() -> None:
    """Load the model before the call, so the first question does not wait for it."""
    transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32))


def listen(source: str = "system", segmenter: Segmenter | None = None, vocabulary: str = "") -> Iterator[Utterance]:
    """Yield finished utterances from one audio source until the helper stops."""
    speaker = "them" if source == "system" else "me"
    segmenter = segmenter or Segmenter()
    warm_up()
    tap = subprocess.Popen([str(AUDIOTAP), source], stdout=subprocess.PIPE)
    assert tap.stdout is not None
    try:
        while chunk := tap.stdout.read(FRAME * 4 * 10):  # ~300 ms per read
            for speech in segmenter.feed(np.frombuffer(chunk, dtype=np.float32)):
                ended = time.perf_counter()
                text = transcribe(speech, vocabulary)
                if text:
                    yield Utterance(speaker, text, len(speech) / SAMPLE_RATE, time.perf_counter() - ended)
    finally:
        tap.terminate()


if __name__ == "__main__":
    import sys

    for u in listen(sys.argv[1] if len(sys.argv) > 1 else "system"):
        print(f"[{u.speaker}] ({u.seconds:.1f}s audio, text in {u.latency:.2f}s) {u.text}", flush=True)


# ── streaming: transcribe while the person is still speaking ─────────────────────────────────

@dataclass(frozen=True)
class Event:
    kind: str  # "partial" while speaking, "final" when the utterance ends
    speaker: str
    text: str
    at: float  # time.perf_counter() when the text was ready
    fast: bool = False  # final taken from the last partial, with no extra transcription
    started: float = 0.0  # time.perf_counter() when this utterance's speech began


class StreamingTranscriber:
    """Partial transcripts while someone speaks; the final one as soon as they stop.

    While an utterance grows, the audio so far is transcribed in the background every
    `partial_every` seconds. When the speaker stops, if the last partial already covers all but
    `fast_margin` seconds of the speech, it becomes the final text at once; otherwise the whole
    utterance is transcribed one more time.
    """

    def __init__(self, source: str = "system", vocabulary: str = "", threshold: float = 0.008,
                 silence_ms: int = 400, partial_every: float = 0.6, fast_margin: float = 0.2,
                 min_seconds: float = 0.6):
        from concurrent.futures import ThreadPoolExecutor

        self.source, self.vocabulary, self.threshold = source, vocabulary, threshold
        self.speaker = "them" if source == "system" else "me"
        self.silence_frames = max(1, silence_ms // 30)
        self.partial_every = int(partial_every * SAMPLE_RATE)
        self.fast_margin = int(fast_margin * SAMPLE_RATE)
        self.min_samples = int(min_seconds * SAMPLE_RATE)
        self.pool = ThreadPoolExecutor(max_workers=1)  # one model, one worker

    def events(self, on_ready=None, on_restart=None) -> Iterator[Event]:
        """`on_ready()` once the model is loaded and audio flows; `on_restart(reason)` if the helper stops
        and is started again. The helper is restarted until the caller stops iterating."""
        self.pool.submit(warm_up).result()
        while True:
            yield from self._run(on_ready)
            if on_restart:
                on_restart("audio capture stopped; restarting")
            time.sleep(1.0)

    def _run(self, on_ready=None) -> Iterator[Event]:
        tap = subprocess.Popen([str(AUDIOTAP), self.source], stdout=subprocess.PIPE)
        assert tap.stdout is not None
        if on_ready:
            on_ready()
        speech: list[np.ndarray] = []
        quiet = 0
        pending = np.zeros(0, dtype=np.float32)
        job = None
        job_covers = 0
        last_partial = ("", 0)  # text, samples covered
        next_partial = self.partial_every
        started = 0.0
        try:
            while chunk := tap.stdout.read(FRAME * 4 * 3):  # ~90 ms per read
                pending = np.concatenate([pending, np.frombuffer(chunk, dtype=np.float32)])
                ended = False
                while len(pending) >= FRAME:
                    frame, pending = pending[:FRAME], pending[FRAME:]
                    loud = float(np.sqrt(np.mean(frame * frame))) > self.threshold
                    if speech or loud:
                        if not speech:
                            started = time.perf_counter()
                        speech.append(frame)
                        quiet = 0 if loud else quiet + 1
                    if speech and quiet >= self.silence_frames:
                        ended = True
                        break
                # a finished background partial
                if job is not None and job.done():
                    last_partial = (job.result(), job_covers)
                    job = None
                    if last_partial[0] and not ended:
                        yield Event("partial", self.speaker, last_partial[0], time.perf_counter(), started=started)
                total = sum(len(f) for f in speech) - quiet * FRAME
                if not ended and speech and job is None and total >= next_partial:
                    audio = np.concatenate(speech)[:total]
                    job, job_covers = self.pool.submit(transcribe, audio, self.vocabulary), total
                    next_partial = total + self.partial_every
                if ended:
                    audio = np.concatenate(speech)[:total]
                    speech, quiet, next_partial = [], 0, self.partial_every
                    if total < self.min_samples:
                        job, last_partial = None, ("", 0)
                        continue
                    if job is not None:  # a partial is running: take it if it is enough
                        job_text = job.result()
                        last_partial, job = (job_text, job_covers), None
                    text, covers = last_partial
                    if text and total - covers <= self.fast_margin:
                        yield Event("final", self.speaker, text, time.perf_counter(), fast=True, started=started)
                    else:
                        text = self.pool.submit(transcribe, audio, self.vocabulary).result()
                        if text:
                            yield Event("final", self.speaker, text, time.perf_counter(), started=started)
                    last_partial = ("", 0)
        finally:
            tap.terminate()
