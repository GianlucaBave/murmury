import re
from pathlib import Path

import pytest

from copilot import material, providers
from copilot.answer import Answer
from copilot.openai_copilot import OpenAICopilot
from evals import faithfulness as f

FIXTURES = Path(f.__file__).parent / "fixtures"
SHEET_A = (FIXTURES / "product-a.md").read_text(encoding="utf-8")


# -- fixtures -----------------------------------------------------------------------------------


def test_the_two_sheets_differ_only_in_the_price():
    a = SHEET_A.splitlines()
    b = (FIXTURES / "product-b.md").read_text(encoding="utf-8").splitlines()
    assert len(a) == len(b)
    different = [(x, y) for x, y in zip(a, b) if x != y]
    assert len(different) == 1
    assert "$120" in different[0][0] and "$145" in different[0][1]


@pytest.mark.parametrize("name", ["product-a.md", "product-b.md"])
def test_neither_sheet_says_anything_about_a_warranty_or_a_period(name):
    text = (FIXTURES / name).read_text(encoding="utf-8").lower()
    assert not re.search(r"warrant|guarant|lifetime|repair|replace", text)
    assert not f.states_period(text)


# -- check 1: price -----------------------------------------------------------------------------


@pytest.mark.parametrize("answer, ok", [
    ("SAY: It costs $120 per lamp, tax not included.", True),
    ("SAY: It is 120 dollars.", True),
    ("SAY: $120.00 per lamp.", True),
    ("SAY: It costs $145 per lamp.", False),                      # the other version's price
    ("SAY: It costs $120, not $145.", False),                     # both prices: not from this sheet alone
    ("SAY: It costs $1,200 for ten lamps.", False),               # 1,200 is not 120
    ("SAY: It costs $1200.", False),
    ("SAY: It costs $120.50.", False),
    ("SAY: I do not have that.", False),
])
def test_check_price(answer, ok):
    assert f.check_price(answer, "120", "145") is ok


# -- check 2: source ----------------------------------------------------------------------------


@pytest.mark.parametrize("answer, ok", [
    ("SAY: $120 per lamp.\n- It costs $120 per lamp [product-a.md]", True),
    ("SAY: $120 per lamp.\n- It costs $120 per lamp [Product-A]", True),
    ("SAY: $120 per lamp.\n- It costs $120 per lamp [Price]", True),                 # a heading of the sheet
    ("SAY: $120 per lamp.\n- It costs $120 per lamp [Price section]", True),
    ("SAY: $120 per lamp.\n- The sheet says price: $120 per lamp, tax not included.", True),  # a quote
    ("SAY: $120 per lamp.\n- It costs $120 per lamp [Lumo L2 Desk Lamp]", True),     # the title of the sheet
    ("SAY: $120 per lamp.\n- It costs $120 per lamp [page 3]", False),               # a tag that points nowhere
    ("SAY: $120 per lamp.\n- It costs $120 per lamp [product sheet]", False),        # vague: no file, no heading
    ("SAY: $120 per lamp.\n- It costs $120 per lamp [p]", False),
    ("SAY: $120 per lamp.\n- It costs $120 per lamp", False),                        # no source at all
    ("SAY: $120 per lamp.\n- It costs $120 per lamp [product-b.md]", False),         # the other file
])
def test_check_source(answer, ok):
    assert f.check_source(answer, "product-a.md", SHEET_A) is ok


# -- check 3: the warranty is not in the document -----------------------------------------------


@pytest.mark.parametrize("answer", [
    "SAY: That is not in our plan yet.",
    "SAY: The sheet does not state a warranty period.\n- Not in plan: the warranty period",
    "SAY: I don't have a warranty period in the product sheet.",
    "SAY: The product sheet doesn't mention a warranty.",
    "SAY: Our sheet shows no warranty information.",
    "SAY: That is not in the document.\n- Not in plan: how many months or years it covers",
    "SAY: The warranty period isn\u2019t stated in the sheet.",
])
def test_a_warranty_answer_that_says_it_is_not_in_the_document_passes(answer):
    assert f.check_not_in_document(answer)


@pytest.mark.parametrize("answer", [
    "SAY: The warranty lasts two years.",
    "SAY: We cover it for 24 months.",
    "SAY: It comes with a 1-year warranty.",
    "SAY: It has a lifetime warranty.",
    "SAY: There is a twelve-month warranty.",
    "SAY: The warranty is 2 years [product-a.md]",
    "SAY: That is not in our plan yet.\n- Most lamps like it carry a 2 year warranty",   # says both: still invented
    "SAY: Our warranty is standard.",                                                   # invents, names no period
    "",
])
def test_a_warranty_answer_that_invents_a_period_or_never_says_it_is_missing_fails(answer):
    assert not f.check_not_in_document(answer)


# -- a whole run, with fake copilots ------------------------------------------------------------


class FakeCopilot:
    """Reads the price out of the sheet in its prompt, like a model that answers from the document."""

    def __init__(self, prompt: str, warranty: str):
        self.prompt, self.warranty, self.history = prompt, warranty, []

    def answer(self, question, before=""):
        if "warranty" in question:
            text = self.warranty
        else:
            price = re.search(r"Price: (\$\d+)", self.prompt).group(1)
            text = f"SAY: The lamp costs {price} per lamp.\n- It is {price} per lamp, tax not included [product sheet]"
        yield text
        yield Answer(question, text, 0.0, 0.0)

    def remember(self, question, answer):
        self.history.append((question, answer))


HONEST = "SAY: That is not in our plan yet."
INVENTED = "SAY: The warranty lasts two years."


def run(warranty: str, runs: int = 1):
    prompts = []

    def make(prompt):
        prompts.append(prompt)
        return FakeCopilot(prompt, warranty)

    return f.evaluate(make, runs), prompts


def test_a_faithful_copilot_passes_all_three_checks_for_both_versions():
    results, _ = run(HONEST)
    assert [r.version for r in results] == ["A", "B"]
    assert all(r.price_ok and r.source_ok and r.warranty_ok for r in results)


def test_an_invented_warranty_fails_check_3_even_when_the_price_is_right():
    results, _ = run(INVENTED)
    for r in results:
        assert r.price_ok and r.source_ok          # checks 1 and 2 are fine
        assert not r.warranty_ok                   # check 3 is the one that catches it


def test_each_version_runs_in_a_fresh_copilot_with_only_its_own_sheet():
    _, prompts = run(HONEST, runs=2)
    assert len(prompts) == 4
    assert all("$120" in p and "$145" not in p for p in prompts[:2])
    assert all("$145" in p and "$120" not in p for p in prompts[2:])


def test_a_copilot_that_ignores_the_sheet_fails_check_1():
    class FromMemory(FakeCopilot):
        def answer(self, question, before=""):
            text = "SAY: It costs $99 per lamp." if "warranty" not in question else HONEST
            yield text
            yield Answer(question, text, 0.0, 0.0)

    results = f.evaluate(lambda prompt: FromMemory(prompt, HONEST))
    assert not any(r.price_ok for r in results)


def test_report_prints_three_scores_per_version_and_says_whether_all_passed(capsys):
    assert f.report(run(HONEST, runs=2)[0]) is True
    out = capsys.readouterr().out
    assert "Version A (sheet says $120), 2 run(s)" in out and "Version B (sheet says $145), 2 run(s)" in out
    assert out.count("1 price") == 2 and out.count("2 source") == 2 and out.count("3 warranty") == 2
    assert "2/2  PASS" in out and "ALL CHECKS PASSED" in out

    assert f.report(run(INVENTED)[0]) is False
    out = capsys.readouterr().out
    assert "3 warranty  0/1  FAIL" in out and "SOME CHECKS FAILED" in out


# -- building the copilot, as the app does ------------------------------------------------------


def test_build_copilot_gives_an_openai_copilot_for_a_local_service_with_only_one_sheet():
    prompt = material.as_prompt(material.load([FIXTURES / "product-b.md"]))
    copilot = f.build_copilot(providers.provider("ollama"), None, "gemma3:12b", prompt)
    assert isinstance(copilot, OpenAICopilot)
    assert copilot.model == "gemma3:12b"
    assert "$145" in copilot.system and "$120" not in copilot.system


def test_main_needs_a_model_for_services_other_than_anthropic(capsys):
    with pytest.raises(SystemExit) as stop:
        f.main(["--provider", "ollama"])
    assert stop.value.code == 2
    assert "--model is required" in capsys.readouterr().err


def test_main_exit_status_follows_the_checks(monkeypatch):
    monkeypatch.setattr(f, "build_copilot", lambda service, key, model, prompt: FakeCopilot(prompt, HONEST))
    assert f.main(["--provider", "ollama", "--model", "x"]) == 0
    monkeypatch.setattr(f, "build_copilot", lambda service, key, model, prompt: FakeCopilot(prompt, INVENTED))
    assert f.main(["--provider", "ollama", "--model", "x"]) == 1