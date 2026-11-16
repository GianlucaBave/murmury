"""Audio sources: capture float32 16 kHz audio streams from local platform helpers.

Encapsulates low-level audio source management behind `open_source(name)` to allow
cross-platform capture implementations (e.g. macOS audiotap, Windows capture #5).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000
FRAME = 480  # 30 ms at 16 kHz
# Default read buffer size (~90 ms, matching 3 frames)
DEFAULT_READ_BYTES = FRAME * 4 * 3

# inside the packaged app the helper sits in the bundle's resources; from source, next to the code
_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
AUDIOTAP = _ROOT / "audiotap" / "audiotap"


@contextmanager
def _open_macos(source: str, chunk_frames: int = 3) -> Iterator[Iterator[np.ndarray]]:
    """Stream 16 kHz float32 chunks from the macOS audiotap helper."""
    tap = subprocess.Popen([str(AUDIOTAP), source], stdout=subprocess.PIPE)
    assert tap.stdout is not None
    chunk_bytes = FRAME * 4 * chunk_frames

    def read_chunks() -> Iterator[np.ndarray]:
        assert tap.stdout is not None
        while chunk := tap.stdout.read(chunk_bytes):
            yield np.frombuffer(chunk, dtype=np.float32)

    try:
        yield read_chunks()
    finally:
        try:
            tap.terminate()
        except OSError:
            pass


@contextmanager
def open_source(name: str = "system", chunk_frames: int = 3) -> Iterator[Iterator[np.ndarray]]:
    """Open an audio source yielding an iterator of float32 16 kHz chunks.

    Deterministic cleanup: terminates the helper process on exit, early break, or exception.
    Platform hook: routes to macOS audiotap, leaving a clear plug-in point for Windows (#5).
    """
    if sys.platform == "darwin":
        with _open_macos(name, chunk_frames=chunk_frames) as stream:
            yield stream
    elif sys.platform == "win32":
        # Windows capture (#5) will plug in here
        raise NotImplementedError("Windows audio capture is not yet implemented (see #5)")
    else:
        with _open_macos(name, chunk_frames=chunk_frames) as stream:
            yield stream

