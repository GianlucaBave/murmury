"""Speech to text: mlx-whisper on macOS, faster-whisper on every other platform.

The backend is chosen from sys.platform each time transcribe() runs, and each library is imported only by
its own backend: macOS never needs faster-whisper, and Windows or Linux never need mlx-whisper.
"""

from __future__ import annotations

import sys
import threading

import numpy as np

MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
# multilingual like the Mac model, so calls in Italian or other languages still work
FASTER_WHISPER_MODEL = "small"

_model = None  # the faster-whisper model, loaded on first use
_model_lock = threading.Lock()


def _skip_word_timing() -> None:
    """mlx-whisper imports numba and scipy only for word-level timestamps, which this tool never asks for.
    A stand-in module keeps them (and about 160 MB) out of the packaged app."""
    if "mlx_whisper.timing" in sys.modules:
        return
    import types

    stub = types.ModuleType("mlx_whisper.timing")

    def add_word_timestamps(*args, **kwargs):
        raise RuntimeError("word timestamps are not included in Murmury")

    stub.add_word_timestamps = add_word_timestamps
    sys.modules["mlx_whisper.timing"] = stub


def _transcribe_mlx(audio: np.ndarray, vocabulary: str) -> str:
    _skip_word_timing()
    import mlx_whisper  # heavy import, kept out of module load

    result = mlx_whisper.transcribe(audio, path_or_hf_repo=MLX_MODEL, condition_on_previous_text=False,
                                    initial_prompt=vocabulary or None)
    return result["text"].strip()


def _faster_whisper_model():
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel  # heavy import, kept out of module load

            _model = WhisperModel(FASTER_WHISPER_MODEL, device="cpu", compute_type="int8")
        return _model


def _transcribe_faster_whisper(audio: np.ndarray, vocabulary: str) -> str:
    segments, _info = _faster_whisper_model().transcribe(
        audio, initial_prompt=vocabulary or None, condition_on_previous_text=False)
    # transcribe() returns a lazy generator: the work happens while the segments are read
    return "".join(segment.text for segment in segments).strip()


def transcribe(audio: np.ndarray, vocabulary: str = "") -> str:
    """`vocabulary`: names and terms the model would otherwise mishear, comma separated
    (without it, an uncommon company name came out as a common word in testing)."""
    backend = _transcribe_mlx if sys.platform == "darwin" else _transcribe_faster_whisper
    return backend(audio, vocabulary)
