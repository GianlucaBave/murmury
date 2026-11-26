"""Check the Windows audio helper: record a few seconds of system audio and report what came out.

Play something (a YouTube video, music, a call) while it runs, then play nothing for the last
seconds; the report covers both cases. Run it from the repo root after building audiotap.exe:

    uv run --with numpy python scripts/check_audiotap_windows.py            # system audio, 8 s
    uv run --with numpy python scripts/check_audiotap_windows.py mic 5      # microphone, 5 s

It also writes audiotap-check.wav (16 kHz mono, 16-bit) so you can listen to what was captured.
Delete the file afterwards: it is a recording of your audio.
"""

from __future__ import annotations

import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000
ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "audiotap" / "audiotap.exe"


def main() -> int:
    source = sys.argv[1] if len(sys.argv) > 1 else "system"
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
    if not EXE.exists():
        print(f"{EXE} not found: build it first (see audiotap/windows/main.cpp)")
        return 1

    print(f"Recording {seconds:.0f} s from '{source}'. Play audio now, then stop it for the last few seconds.")
    tap = subprocess.Popen([str(EXE), source], stdout=subprocess.PIPE)
    assert tap.stdout is not None
    chunks: list[bytes] = []
    started = time.perf_counter()
    first_byte = None
    while time.perf_counter() - started < seconds:
        chunk = tap.stdout.read(4 * 480 * 3)
        if not chunk:
            break
        if first_byte is None:
            first_byte = time.perf_counter() - started
        chunks.append(chunk)
    elapsed = time.perf_counter() - started
    tap.terminate()

    raw = b"".join(chunks)
    problems = []
    if len(raw) % 4:
        problems.append(f"byte count {len(raw)} is not a multiple of 4: samples are misaligned")
    audio = np.frombuffer(raw[: len(raw) // 4 * 4], dtype="<f4")
    expected = elapsed * SAMPLE_RATE
    ratio = len(audio) / expected if expected else 0.0
    if not 0.9 <= ratio <= 1.1:
        problems.append(f"got {len(audio)} samples, expected about {expected:.0f} (ratio {ratio:.2f}): wrong rate or gaps")
    if not np.isfinite(audio).all():
        problems.append("NaN or infinite samples")
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 1.5:
        problems.append(f"peak {peak:.2f} is far above 1.0: scaling is wrong")

    frames = len(audio) // 480
    rms = np.sqrt((audio[: frames * 480].reshape(frames, 480) ** 2).mean(axis=1)) if frames else np.zeros(0)
    loud = float((rms > 0.008).mean()) if frames else 0.0  # same threshold the segmenter uses
    print(f"samples: {len(audio)}  (~{len(audio) / SAMPLE_RATE:.1f} s of audio in {elapsed:.1f} s)")
    print(f"first data after: {first_byte:.2f} s" if first_byte is not None else "no data at all")
    print(f"peak: {peak:.3f}   frames above speech threshold: {loud:.0%}")
    if frames:
        quiet_tail = int(np.argmax(rms[::-1] > 0.008)) if (rms > 0.008).any() else frames
        print(f"quiet frames at the end: {quiet_tail} (the segmenter needs about 13 to end an utterance)")

    wav = ROOT / "audiotap-check.wav"
    with wave.open(str(wav), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
    print(f"wrote {wav}")

    if problems:
        print("\nPROBLEMS:\n- " + "\n- ".join(problems))
        return 1
    print("\nformat looks right")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())