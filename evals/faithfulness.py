"""Faithfulness eval: does the answer come from the loaded document, or from the model's memory?

Two copies of a made-up product sheet (evals/fixtures) are identical except for the price: A says $120,
B says $145. Each runs in a fresh copilot with only its own version loaded. The copilot is asked the price,
then the warranty period, which neither sheet states. Three things are scored separately, because a
correct price can sit next to an invented warranty:

  1. price     the right price for that version (and not the other version's price)
  2. source    a source tag or a quote that points into the loaded sheet
  3. warranty  the warranty answer says it is not in the document and states no period

Checks 1 and 2 are string matching and check 3 is a phrase and pattern match: no grader model is used, so
a run costs only the answers (a few cents with an API key, nothing with a local model).

    uv run python -m evals.faithfulness --provider ollama --model gemma3:12b
    uv run python -m evals.faithfulness --provider anthropic --model claude-haiku-4-5 --runs 3

--provider and --model work as in the app (copilot/providers.py). Exit status is 1 if any check failed.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from copilot import material, providers
from copilot.answer import Answer

FIXTURES = Path(__file__).parent / "fixtures"
SITUATION = "a sales call with a prospective customer"
PRICE_QUESTION = "How much does the lamp cost?"
WARRANTY_QUESTION = "And how long is the warranty?"


@dataclass(frozen=True)
class Version:
    label: str
    file: str
    price: str  # digits as the sheet writes them, e.g. "120"


VERSIONS = (Version("A", "product-a.md", "120"), Version("B", "product-b.md", "145"))


@dataclass(frozen=True)
class Result:
    version: str
    price_answer: str
    warranty_answer: str
    price_ok: bool
    source_ok: bool
    warranty_ok: bool


# -- the three checks ---------------------------------------------------------------------------


def _normal(text: str) -> str:
    return text.replace("\u2019", "'").replace("\u2018", "'").lower()


def mentions_price(text: str, amount: str) -> bool:
    """The amount as a whole number: 120, $120, $120.00, but not 1,200 or 1200 or 120.5."""
    return re.search(rf"(?<![\d,.]){re.escape(amount)}(?:\.00)?(?![\d,]|\.\d)", text) is not None


def check_price(answer: str, right: str, wrong: str) -> bool:
    """Check 1: the right price is in the answer and the other version's price is not."""
    return mentions_price(answer, right) and not mentions_price(answer, wrong)


def _words(text: str) -> list[str]:
    return re.findall(r"[\w$.,]+", _normal(text).replace("*", " "))


def _clean(words: list[str]) -> list[str]:
    return [w.strip(".,") for w in words if w.strip(".,")]


def check_source(answer: str, name: str, sheet: str) -> bool:
    """Check 2: a [tag] that names the file or one of its headings, or a quote of four or more words in a row.

    The answer instructions ask for the source in square brackets at the end of each line.
    """
    headings = [h.lower() for h in re.findall(r"^#+\s*(.+?)\s*$", sheet, flags=re.M)]
    names = {name.lower(), Path(name).stem.lower()}
    for tag in re.findall(r"\[([^\]]+)\]", _normal(answer)):
        if any(n in tag for n in names) or any(h in tag for h in headings):
            return True
    answer_words, sheet_words = _clean(_words(answer)), _clean(_words(sheet))
    sheet_runs = {tuple(sheet_words[i:i + 4]) for i in range(len(sheet_words) - 3)}
    return any(tuple(answer_words[i:i + 4]) in sheet_runs for i in range(len(answer_words) - 3))


NOT_IN_DOCUMENT = re.compile(
    r"not in (?:our |the |this )?(?:plan|document|doc|sheet|product sheet|material|file|spec)"
    r"|not (?:stated|mentioned|specified|listed|covered|given|provided|included|available)"
    r"|(?:doesn't|does not|don't|do not|isn't|is not|aren't|are not|didn't|did not)"
    r" (?:say|state|mention|specify|list|cover|give|provide|contain|include|have|show|spell)"
    r"|(?:no|nothing) (?:warranty|information|details?|figures?|period|word|mention)"
    r"|nothing (?:in|about|on)\b"
)

WARRANTY_PERIOD = re.compile(
    r"\b(?:\d+(?:[.,]\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a|an)"
    r"[\s-]*(?:to[\s-]*\w+[\s-]*)?(?:day|week|month|year)s?\b"
    r"|\blifetime\b"
)


def states_period(text: str) -> bool:
    """A length of time ("2 years", "twelve-month", "a year", "lifetime") that the sheet never gave."""
    return WARRANTY_PERIOD.search(_normal(text)) is not None


def check_not_in_document(answer: str) -> bool:
    """Check 3: the answer says the warranty is not in the document and does not state a period.

    A period fails the check even when "not in the document" is also said: that is the invention.
    """
    text = _normal(answer)
    return NOT_IN_DOCUMENT.search(text) is not None and not states_period(text)


# -- running the copilot ------------------------------------------------------------------------


def ask(copilot, question: str) -> str:
    """One question, the way the app asks it: the finished answer is remembered for the next turn."""
    answer = next(p for p in list(copilot.answer(question)) if isinstance(p, Answer))
    copilot.remember(question, answer.text)
    return answer.text


def evaluate(make_copilot: Callable[[str], object], runs: int = 1, versions=VERSIONS,
             fixtures: Path = FIXTURES) -> list[Result]:
    """Each version, each run, in a fresh copilot that has only that version's sheet loaded."""
    wrong = {v.label: next(o.price for o in versions if o is not v) for v in versions}
    results = []
    for version in versions:
        sources = material.load([fixtures / version.file])
        prompt = material.as_prompt(sources)
        for _ in range(runs):
            copilot = make_copilot(prompt)
            price = ask(copilot, PRICE_QUESTION)
            warranty = ask(copilot, WARRANTY_QUESTION)
            results.append(Result(
                version.label, price, warranty,
                check_price(price, version.price, wrong[version.label]),
                check_source(price, version.file, sources[0].text),
                check_not_in_document(warranty)))
    return results


def build_copilot(service: providers.Provider, key: str | None, model: str, prompt: str):
    """The same copilot the app builds for this service (copilot/app.py, start())."""
    if service.id == "anthropic":
        from copilot.answer import Copilot, client
        return Copilot(prompt, SITUATION, model, client(key))
    from copilot.openai_copilot import OpenAICopilot
    return OpenAICopilot(prompt, SITUATION, service, key or "local", model)


# -- report -------------------------------------------------------------------------------------

CHECKS = (("1 price", "price_ok"), ("2 source", "source_ok"), ("3 warranty", "warranty_ok"))


def report(results: list[Result], show_answers: bool = False) -> bool:
    """Print the three scores for each version; True if every check passed in every run."""
    all_passed = True
    for version in VERSIONS:
        mine = [r for r in results if r.version == version.label]
        if not mine:
            continue
        print(f"Version {version.label} (sheet says ${version.price}), {len(mine)} run(s)")
        for title, attribute in CHECKS:
            passed = sum(getattr(r, attribute) for r in mine)
            all_passed &= passed == len(mine)
            print(f"  {title:<11} {passed}/{len(mine)}  {'PASS' if passed == len(mine) else 'FAIL'}")
        if show_answers:
            for number, r in enumerate(mine, 1):
                print(f"  run {number}\n    price: {r.price_answer.strip()!r}\n    warranty: {r.warranty_answer.strip()!r}")
        print()
    print("ALL CHECKS PASSED" if all_passed else "SOME CHECKS FAILED")
    return all_passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Do the answers come from the loaded document?")
    parser.add_argument("--provider", choices=[p.id for p in providers.PROVIDERS], default=providers.DEFAULT,
                        help="the AI service, as in the app (default: anthropic)")
    parser.add_argument("--model", default=None, help="answer model (default for anthropic: claude-sonnet-5-5)")
    parser.add_argument("--runs", type=int, default=1, help="runs per version; scores are passed/runs")
    parser.add_argument("--show-answers", action="store_true", help="print each answer")
    args = parser.parse_args(argv)

    service = providers.provider(args.provider)
    model = args.model or ("claude-sonnet-5-5" if service.id == "anthropic" else None)
    if not model:
        parser.error(f"--model is required for {service.id} (for example gemma3:12b on ollama)")
    key = providers.api_key(service.id)[0]
    if service.key_required and not key:
        parser.error(f"no {service.name} key: set {' or '.join(service.env)}, or save one on the app's setup screen")

    results = evaluate(lambda prompt: build_copilot(service, key, model, prompt), max(args.runs, 1))
    return 0 if report(results, args.show_answers) else 1


if __name__ == "__main__":
    sys.exit(main())