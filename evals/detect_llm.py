"""The big-model baseline for the question detector: the same 80 lines through evals/skip.py.

It calls skip.evaluate (the code path the app uses), once for the development lines and once for
the held-out lines, and prints the two counts and the time per line in the table format of
evals.detect. Nothing here is tuned on the held-out lines.

    uv run python -m evals.detect_llm --model gemma3:4b

Time per line is the median time to the SKIP (skipped lines) or to the first word (answered
lines), as in evals/skip.py. It is not the time to the end of an answer.
"""

from __future__ import annotations

import argparse
import statistics
import sys

import openai

from copilot import providers
from evals.detect import HELDOUT
from evals.faithfulness import build_copilot
from evals.skip import ANSWER, LINES, SKIP, Result, evaluate, report

COLUMNS = ("Detector", "Lines", "Answered when it should skip", "Skipped when it should answer",
           "Accuracy", "Time per line")


def row(name: str, label: str, results: list[Result]) -> list[str]:
    """One table row, with the same counts as the other detectors."""
    should_skip = sum(r.line.expect == SKIP for r in results)
    should_answer = sum(r.line.expect == ANSWER for r in results)
    wrong = sum(r.false_answer or r.false_skip for r in results)
    return [name, f"{label} ({len(results)})",
            f"{sum(r.false_answer for r in results)}/{should_skip}",
            f"{sum(r.false_skip for r in results)}/{should_answer}",
            f"{100 * (len(results) - wrong) / len(results):.1f}%",
            f"{statistics.median(r.seconds for r in results):.2f} s"]


def table(rows: list[list[str]]) -> str:
    grid = [list(COLUMNS)] + rows
    widths = [max(len(item[i]) for item in grid) for i in range(len(COLUMNS))]
    lines = [" ".join(cell.ljust(w) for cell, w in zip(item, widths)).rstrip() for item in grid]
    lines.insert(1, " ".join("-" * w for w in widths))
    return "\n".join(lines)


def markdown(rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    return "\n".join(lines + ["| " + " | ".join(item) + " |" for item in rows])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The big model as a question detector, on both line sets.")
    parser.add_argument("--provider", choices=[p.id for p in providers.PROVIDERS], default="ollama")
    parser.add_argument("--model", required=True)
    args = parser.parse_args(argv)
    service = providers.provider(args.provider)
    if service.id == "anthropic":
        parser.error("Anthropic has no SKIP to measure; pick ollama, lm-studio or another OpenAI-format service")
    key = providers.api_key(service.id)[0]
    rows: list[list[str]] = []
    for label, path in (("development", LINES), ("held-out", HELDOUT)):
        try:
            results = evaluate(lambda prompt: build_copilot(service, key, args.model, prompt), 1, path)
        except openai.OpenAIError as error:
            where = "" if service.key_required else f" (is it running at {service.base_url}?)"
            print(f"Could not run {args.model} on {service.name}{where}: {error}", file=sys.stderr)
            return 2
        print()
        report(results, f"{args.model} on {service.name}, {label}")
        rows.append(row(args.model, label, results))
    print(f"\n{table(rows)}\n\n{markdown(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
