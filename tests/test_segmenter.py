"""Tests for the speech segmenter in copilot/listen.py.

All audio is synthesized (a sine wave for speech, zeros for silence) at SAMPLE_RATE,
in whole 30 ms frames, so speech and silence never straddle a frame boundary;
feeding in awkward chunk sizes is exercised separately.
"""

import numpy as np

from copilot.listen import FRAME, SAMPLE_RATE, Segmenter


def sine(frames: int, amplitude: float = 0.2) -> np.ndarray:
    """`frames` 30 ms frames of a 440 Hz sine: RMS ≈ amplitude/√2, far above the threshold."""
    t = np.arange(frames * FRAME, dtype=np.float64) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


def silence(frames: int) -> np.ndarray:
    return np.zeros(frames * FRAME, dtype=np.float32)


def feed_all(segmenter: Segmenter, chunks) -> list[np.ndarray]:
    lines = []
    for chunk in chunks:
        lines.extend(segmenter.feed(chunk))
    return lines


def test_silence_alone_gives_nothing():
    segmenter = Segmenter()
    assert feed_all(segmenter, [silence(100)]) == []
    # the same silence arriving in single-frame reads never starts a line either
    assert feed_all(segmenter, [silence(1) for _ in range(300)]) == []


def test_speech_then_enough_silence_gives_one_line_without_the_trailing_silence():
    segmenter = Segmenter(silence_ms=700)  # 700 // 30 = 23 quiet frames cut a line
    lines = feed_all(segmenter, [sine(33), silence(23)])
    assert len(lines) == 1
    assert len(lines[0]) == 33 * FRAME  # the trailing silence is not part of the line
    tail = lines[0][-FRAME:]
    assert float(np.sqrt(np.mean(tail * tail))) > segmenter.threshold  # the line ends on speech
    assert feed_all(segmenter, [silence(50)]) == []  # yet more silence yields no second line


def test_a_pause_shorter_than_silence_ms_keeps_one_line():
    # a pause of 1, 10 or 22 quiet frames stays below the 23 needed to cut
    for pause in (1, 10, 22):
        segmenter = Segmenter(silence_ms=700)
        lines = feed_all(segmenter, [sine(33), silence(pause), sine(33), silence(30)])
        assert len(lines) == 1, pause
        assert len(lines[0]) == (66 + pause) * FRAME, pause  # the pause is inside the line


def test_speech_longer_than_max_seconds_is_cut():
    segmenter = Segmenter(max_seconds=1.0, silence_ms=700)  # 1.0 s = 33 frames per line
    lines = feed_all(segmenter, [sine(66), silence(30)])
    assert len(lines) == 2
    assert [len(line) for line in lines] == [33 * FRAME, 33 * FRAME]  # cut every max_seconds


def test_a_blip_shorter_than_min_seconds_is_dropped():
    segmenter = Segmenter(min_seconds=0.6, silence_ms=700)  # 0.6 s = 20 frames to keep a line
    assert feed_all(segmenter, [sine(5), silence(40)]) == []
    lines = feed_all(segmenter, [sine(33), silence(30)])  # and the segmenter still works after it
    assert len(lines) == 1
    assert len(lines[0]) == 33 * FRAME


def test_the_same_audio_in_small_odd_sized_chunks_gives_the_same_result():
    one_go = np.concatenate([sine(40), silence(8), sine(25), silence(40)])

    by_frame = [one_go[i:i + FRAME] for i in range(0, len(one_go), FRAME)]
    sizes = (1, 7, 333, 17, 1023, 3, 101)
    odd, i, k = [], 0, 0
    while i < len(one_go):
        odd.append(one_go[i:i + sizes[k % len(sizes)]])
        i, k = i + sizes[k % len(sizes)], k + 1

    expected = feed_all(Segmenter(), [one_go])
    assert len(expected) == 1  # the 8-frame pause is shorter than silence_ms, so one line of 73 frames
    assert len(expected[0]) == 73 * FRAME

    for chunks in (by_frame, odd):
        lines = feed_all(Segmenter(), chunks)
        assert len(lines) == len(expected)
        for line, want in zip(lines, expected):
            assert np.array_equal(line, want)
