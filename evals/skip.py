"""Skip eval: does a model stay quiet when a line is not a question, and answer when it is?

With Ollama, LM Studio and every other OpenAI-format service there is no separate question check: the answer
model itself replies SKIP when the last line heard is not a question (copilot/openai_copilot.py, gatekeeps).
Two mistakes are possible, and they cost different things in a call:

  answered when it should skip    small talk fills the window with noise
  skipped when it should answer   a real question gets nothing

evals/fixtures/skip-lines.json holds 40 call lines about the made-up product sheet that evals/faithfulness.py
also uses: 20 that need an answer (questions, requests, follow-ups like "and the height?", questions the sheet
cannot answer) and 20 that do not (greetings, "can you hear me", "let me share my screen", thinking aloud,
thanks, small talk). Each line goes through the same copilot the app builds (copilot/app.py, start()) and the
same code that decides what the window shows (pipeline.respond). Every line stands alone: the copilot's memory
of earlier answers is cleared, and only the line before it, where the fixture gives one, is passed.

Besides the two counts, it prints the time to the SKIP and the time to the first word, as the window would
show them. An empty reply counts as a skip, because the window would show nothing.

    uv run python -m evals.skip --provider ollama --model gemma3:12b
    uv run python -m evals.skip --provider lm-studio --model qwen3-8b --runs 3

--provider and --model work as in the app (copilot/providers.py). Anthropic is not measured: it has its own
question check (Claude Haiku) instead of a SKIP. The exit status is 0 when the run finished, whatever the
counts: they are a measurement, not a pass or fail.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import openai

from copilot import material, pipeline, providers
from evals.faithfulness import SITUATION, build_copilot

FIXTURES = Path(__file__).parent / "fixtures"
LINES = FIXTURES / "skip-lines.json"
ANSWER, SKIP = "answer", "skip"


@dataclass(frozen=True)
class Line:
    text: str
    expect: str  # ANSWER or SKIP
    kind: str    # greeting, follow-up, ...: for reading the misses
    before: str = ""  # the line heard just before, as the app passes it


@dataclass(frozen=True)
class Result:
    line: Line
    answered: bool
    seconds: float  # from the call to the SKIP, or to the first text
    shown: str      # what the window would have shown ("" when skipped)

    @property
    def false_answer(self) -> bool:
        return self.answered and self.line.expect == SKIP

    @property
    def false_skip(self) -> bool:
        return not self.answered and self.line.expect == ANSWER


def load(path: Path = LINES) -> tuple[Path, list[Line]]:
    """The document the lines are about, and the lines."""
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = [Line(e["line"], e["expect"], e["kind"], e.get("before", "")) for e in data["lines"]]
    wrong = [line.text for line in lines if line.expect not in (ANSWER, SKIP)]
    if wrong:
        raise ValueError(f"expect must be {ANSWER!r} or {SKIP!r}: {wrong}")
    return path.parent / data["document"], lines


# -- running the copilot ------------------------------------------------------------------------


def run_line(copilot, line: Line) -> Result:
    """One line through pipeline.respond, the code the app uses: was it answered, and how soon."""
    copilot.history = []  # every line stands alone
    started = time.perf_counter()
    first, shown = None, ""
    for show in pipeline.respond(copilot, line.text, line.before):
        if show.kind == "dropped":
            return Result(line, False, show.at - started, "")
        if first is None:
            first = show.at - started
        if show.kind == "live-done":
            shown = show.text
    return Result(line, bool(shown.strip()), first or 0.0, shown)


def evaluate(make_copilot, runs: int = 1, path: Path = LINES) -> list[Result]:
    """Every line, `runs` times, in one copilot that has only the document loaded."""
    document, lines = load(path)
    copilot = make_copilot(material.as_prompt(material.load([document])))
    if not getattr(copilot, "gatekeeps", False):
        raise ValueError("this copilot has a separate question check; the eval measures copilots that reply SKIP")
    warm = getattr(copilot, "warm", None)
    if warm:
        warm()  # the first call loads a local model: that is not what a line costs during a call
    return [run_line(copilot, line) for _ in range(runs) for line in lines]


# -- report -------------------------------------------------------------------------------------


def _times(label: str, results: list[Result]) -> str:
    if not results:
        return f"{label:<19} none"
    seconds = [r.seconds for r in results]
    return f"{label:<19} median {statistics.median(seconds):.2f} s, slowest {max(seconds):.2f} s ({len(seconds)} lines)"


def _clip(text: str, width: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width - 3] + "..."


def report(results: list[Result], label: str = "") -> None:
    """The two counts, the two times, and every line that went wrong."""
    should_skip = [r for r in results if r.line.expect == SKIP]
    should_answer = [r for r in results if r.line.expect == ANSWER]
    false_answers = [r for r in results if r.false_answer]
    false_skips = [r for r in results if r.false_skip]
    if label:
        print(f"{label}, {len(results)} lines\n")
    print(f"Answered when it should skip   {len(false_answers)}/{len(should_skip)}   (noise in the window)")
    print(f"Skipped when it should answer  {len(false_skips)}/{len(should_answer)}   (a real question gets nothing)")
    print()
    print(_times("Time to SKIP", [r for r in results if not r.answered]))
    print(_times("Time to first word", [r for r in results if r.answered]))
    wrong = false_answers + false_skips
    if wrong:
        print("\nWrong:")
        for r in wrong:
            what = "answered, should skip" if r.false_answer else "skipped, should answer"
            reply = f" -> {_clip(r.shown)!r}" if r.answered else ""
            print(f"  {what} [{r.line.kind}] {r.line.text!r}{reply}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Does the model stay quiet when a line is not a question?")
    parser.add_argument("--provider", choices=[p.id for p in providers.PROVIDERS], default="ollama",
                        help="the AI service, as in the app (default: ollama; not anthropic)")
    parser.add_argument("--model", required=True, help="the answer model, for example gemma3:12b on ollama")
    parser.add_argument("--runs", type=int, default=1, help="times each line is run; counts are out of lines x runs")
    args = parser.parse_args(argv)

    service = providers.provider(args.provider)
    if service.id == "anthropic":
        parser.error("Anthropic has a separate question check (Claude Haiku) and no SKIP to measure; "
                     "pick ollama, lm-studio or another OpenAI-format service")
    key = providers.api_key(service.id)[0]
    if service.key_required and not key:
        parser.error(f"no {service.name} key: set {' or '.join(service.env)}, or save one on the app's setup screen")

    try:
        results = evaluate(lambda prompt: build_copilot(service, key, args.model, prompt), max(args.runs, 1))
    except openai.OpenAIError as error:
        where = "" if service.key_required else f" (is it running at {service.base_url}?)"
        print(f"Could not run {args.model} on {service.name}{where}: {error}", file=sys.stderr)
        return 2
    report(results, f"{args.model} on {service.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
