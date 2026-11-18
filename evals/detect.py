"""Question detectors measured against the skip eval's labelled call lines.

evals/skip.py asks whether a big model stays quiet on lines that are not questions. This script asks how far a
small, fast detector gets on the same lines, on any computer: no model, no network. It counts the same two
mistakes, which cost different things in a call:

  answered when it should skip    small talk fills the window with noise
  skipped when it should answer   a real question gets nothing

and it times each detector per line.

evals/fixtures/skip-lines.json is the development set: detectors are built by looking at it.
evals/fixtures/skip-lines-heldout.json was written before any detector beyond the "?" rule and is never used
to tune one, so by default its misses are only counted, not listed: reading them would be tuning on them.

    uv run python -m evals.detect
    uv run python -m evals.detect --show-heldout-errors    # for the final analysis only
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from evals.skip import ANSWER, FIXTURES, LINES, SKIP, Line, load

HELDOUT = FIXTURES / "skip-lines-heldout.json"

Detector = Callable[[Line], bool]  # True when the line needs an answer


def question_mark(line: Line) -> bool:
    """The floor: a line is a question when it ends with a question mark."""
    return line.text.strip().endswith("?")


DETECTORS: dict[str, Detector] = {"question mark": question_mark}


@dataclass(frozen=True)
class Score:
    detector: str
    lines_name: str
    lines: list[Line]
    false_answers: list[Line]  # answered when it should skip
    false_skips: list[Line]    # skipped when it should answer
    microseconds: float        # per line

    @property
    def accuracy(self) -> float:
        if not self.lines:
            return 0.0
        wrong = len(self.false_answers) + len(self.false_skips)
        return 100 * (len(self.lines) - wrong) / len(self.lines)


def run(detector: Detector, lines: list[Line]) -> tuple[list[Line], list[Line]]:
    """The lines answered when they should skip, and the lines skipped when they should answer."""
    false_answers = [line for line in lines if line.expect == SKIP and detector(line)]
    false_skips = [line for line in lines if line.expect == ANSWER and not detector(line)]
    return false_answers, false_skips


def microseconds_per_line(detector: Detector, lines: list[Line], passes: int = 5, repeats: int = 200) -> float:
    """Time of one line: the median of `passes` measurements, each over `repeats` runs through all the lines."""
    if not lines:
        return 0.0
    per_line = []
    for _ in range(passes):
        started = time.perf_counter()
        for _ in range(repeats):
            for line in lines:
                detector(line)
        per_line.append((time.perf_counter() - started) / (repeats * len(lines)))
    return statistics.median(per_line) * 1e6


def score(name: str, detector: Detector, lines_name: str, lines: list[Line]) -> Score:
    false_answers, false_skips = run(detector, lines)
    return Score(name, lines_name, lines, false_answers, false_skips, microseconds_per_line(detector, lines))


# -- report -------------------------------------------------------------------------------------

COLUMNS = ("Detector", "Lines", "Answered when it should skip", "Skipped when it should answer",
           "Accuracy", "Time per line")


def row(result: Score) -> list[str]:
    should_skip = sum(line.expect == SKIP for line in result.lines)
    should_answer = sum(line.expect == ANSWER for line in result.lines)
    return [result.detector, f"{result.lines_name} ({len(result.lines)})",
            f"{len(result.false_answers)}/{should_skip}", f"{len(result.false_skips)}/{should_answer}",
            f"{result.accuracy:.1f}%", f"{result.microseconds:.1f} us"]


def table(rows: list[list[str]]) -> str:
    """The rows as aligned text."""
    grid = [list(COLUMNS)] + rows
    widths = [max(len(r[i]) for r in grid) for i in range(len(COLUMNS))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(r, widths)).rstrip() for r in grid]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def markdown_table(rows: list[list[str]]) -> str:
    """The same rows as a Markdown table, to paste into a pull request."""
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def wrong_lines(result: Score) -> str:
    """Every line the detector got wrong, with its kind, to read the misses."""
    out = [f"{result.detector}, {result.lines_name} lines, wrong:"]
    out += [f"  answered, should skip [{line.kind}] {line.text!r}" for line in result.false_answers]
    out += [f"  skipped, should answer [{line.kind}] {line.text!r}" for line in result.false_skips]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="How far does a small question detector get on the skip eval's lines?")
    parser.add_argument("--show-heldout-errors", action="store_true",
                        help="also list the held-out lines a detector got wrong (for the final analysis only)")
    args = parser.parse_args(argv)

    sets = {"development": load(LINES)[1], "held-out": load(HELDOUT)[1]}
    scores = [score(name, detector, lines_name, lines)
              for name, detector in DETECTORS.items() for lines_name, lines in sets.items()]
    rows = [row(result) for result in scores]
    print(f"{table(rows)}\n\n{markdown_table(rows)}")
    for result in scores:
        if result.lines_name == "development" or args.show_heldout_errors:
            print(f"\n{wrong_lines(result)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
