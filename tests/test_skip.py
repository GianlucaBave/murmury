import time

import openai
import pytest

from copilot import material, providers
from copilot.answer import Answer
from copilot.claude_code import GATE
from copilot.openai_copilot import OpenAICopilot
from evals import skip as s

DOCUMENT, LINES = s.load()
EXPECT = {line.text: line.expect for line in LINES}


# -- the fixture --------------------------------------------------------------------------------


def test_the_fixture_has_forty_lines_half_to_answer_and_half_to_skip():
    assert len(LINES) == 40
    assert sum(line.expect == s.ANSWER for line in LINES) == 20
    assert sum(line.expect == s.SKIP for line in LINES) == 20


def test_every_line_is_unique_and_not_empty():
    texts = [line.text for line in LINES]
    assert all(t.strip() for t in texts)
    assert len(set(texts)) == len(texts)


def test_the_fixture_covers_the_kinds_of_line_the_issue_names():
    kinds = {line.kind for line in LINES}
    assert {"question", "follow-up", "greeting", "audio check", "screen share", "thinking aloud"} <= kinds
    assert all(line.before for line in LINES if line.kind == "follow-up")  # a follow-up means little alone


def test_the_document_the_lines_are_about_loads():
    assert DOCUMENT.name == "product-a.md"
    assert "Lumo L2" in material.as_prompt(material.load([DOCUMENT]))


def test_an_expect_other_than_answer_or_skip_is_refused(tmp_path):
    bad = tmp_path / "lines.json"
    bad.write_text('{"document": "x.md", "lines": [{"line": "Hi", "expect": "ignore", "kind": "greeting"}]}',
                   encoding="utf-8")
    with pytest.raises(ValueError, match="expect must be"):
        s.load(bad)


# -- fake copilots ------------------------------------------------------------------------------


class FakeCopilot:
    """Replies to each line from `reply(line)`, in the chunks it returns, like a model that streams."""

    gatekeeps = True

    def __init__(self, prompt: str, reply, delay: float = 0.0):
        self.prompt, self.reply, self.delay = prompt, reply, delay
        self.history, self.calls = [], []

    def answer(self, question, before=""):
        self.calls.append((question, before, list(self.history)))
        parts = self.reply(question)
        text = "".join(parts)
        time.sleep(self.delay)
        yield from parts
        yield Answer(question, text, 0.0, 0.0)


def answer_text(question):
    return ["SAY: ", "It is $120 per lamp."]


def perfect(question):
    return ["SKIP"] if EXPECT[question] == s.SKIP else answer_text(question)


def run(reply, runs: int = 1):
    copilots = []

    def make(prompt):
        copilots.append(FakeCopilot(prompt, reply))
        return copilots[0]

    return s.evaluate(make, runs), copilots[0]


# -- scoring ------------------------------------------------------------------------------------


def test_a_copilot_that_gets_every_line_right_has_no_wrong_lines():
    results, _ = run(perfect)
    assert len(results) == 40
    assert not any(r.false_answer or r.false_skip for r in results)


def test_a_copilot_that_answers_everything_makes_twenty_false_answers_and_no_false_skips():
    results, _ = run(answer_text)
    assert sum(r.false_answer for r in results) == 20
    assert sum(r.false_skip for r in results) == 0


def test_a_copilot_that_skips_everything_makes_twenty_false_skips_and_no_false_answers():
    results, _ = run(lambda question: ["SKIP"])
    assert sum(r.false_skip for r in results) == 20
    assert sum(r.false_answer for r in results) == 0


def test_each_kind_of_mistake_is_counted_on_its_own_line():
    chatty = "Hi, thanks for joining everyone."
    quiet = "How much does the lamp cost?"

    def reply(question):
        if question == chatty:
            return answer_text(question)   # small talk answered
        if question == quiet:
            return ["SKIP"]                 # a real question skipped
        return perfect(question)

    results, _ = run(reply)
    assert [r.line.text for r in results if r.false_answer] == [chatty]
    assert [r.line.text for r in results if r.false_skip] == [quiet]


@pytest.mark.parametrize("reply", [["SKIP"], ["skip"], ["SKIP."], ["SK", "IP"], ["  Skip"]])
def test_a_skip_is_recognised_as_the_app_recognises_it_also_when_it_streams_in_pieces(reply):
    results, _ = run(lambda question: reply)
    assert not any(r.answered for r in results)


def test_an_empty_reply_counts_as_a_skip_because_the_window_shows_nothing():
    results, _ = run(lambda question: [""])
    assert not any(r.answered for r in results)
    assert sum(r.false_skip for r in results) == 20


def test_what_the_window_would_show_is_kept_for_an_answered_line():
    results, _ = run(answer_text)
    assert all(r.shown == "SAY: It is $120 per lamp." for r in results)


# -- how each line is run -----------------------------------------------------------------------


def test_every_line_is_asked_with_the_line_before_it_and_no_memory_of_earlier_answers():
    results, copilot = run(perfect)
    asked = {question: (before, history) for question, before, history in copilot.calls}
    assert len(copilot.calls) == 40
    for line in LINES:
        assert asked[line.text] == (line.before, [])


def test_the_memory_of_the_copilot_is_cleared_before_each_line():
    copilot = FakeCopilot("", perfect)
    copilot.history = [("earlier question", "earlier answer")]
    s.run_line(copilot, LINES[0])
    assert copilot.calls[0][2] == []


def test_runs_repeats_every_line_in_the_same_copilot():
    results, copilot = run(perfect, runs=3)
    assert len(results) == 120 and len(copilot.calls) == 120
    assert copilot.prompt.count("Lumo L2") >= 1


def test_the_copilot_gets_only_the_document_the_lines_are_about():
    _, copilot = run(perfect)
    assert "Price: $120" in copilot.prompt and "$145" not in copilot.prompt


def test_a_copilot_with_its_own_question_check_is_refused():
    class Separate(FakeCopilot):
        gatekeeps = False

    with pytest.raises(ValueError, match="separate question check"):
        s.evaluate(lambda prompt: Separate(prompt, perfect))


def test_the_copilot_is_warmed_up_once_before_any_line_is_timed():
    events = []

    class Warm(FakeCopilot):
        def warm(self):
            events.append("warm")

        def answer(self, question, before=""):
            events.append("line")
            yield from super().answer(question, before)

    s.evaluate(lambda prompt: Warm(prompt, perfect))
    assert events[0] == "warm" and events.count("warm") == 1 and events.count("line") == 40


# -- time ---------------------------------------------------------------------------------------


def test_the_time_to_the_first_word_is_measured_from_the_call():
    copilot = FakeCopilot("", answer_text, delay=0.05)
    result = s.run_line(copilot, LINES[0])
    assert 0.04 <= result.seconds < 2


def test_the_time_to_a_skip_is_measured_from_the_call():
    copilot = FakeCopilot("", lambda question: ["SKIP"], delay=0.05)
    result = s.run_line(copilot, LINES[0])
    assert not result.answered
    assert 0.04 <= result.seconds < 2


# -- report -------------------------------------------------------------------------------------


def result(text, expect, answered, seconds, kind="question", shown=""):
    return s.Result(s.Line(text, expect, kind), answered, seconds, shown)


def test_report_prints_both_counts_the_times_and_the_wrong_lines(capsys):
    results = [
        result("Hi", s.SKIP, False, 0.2),
        result("Let me share my screen.", s.SKIP, True, 0.6, "screen share", "SAY: Sure, go ahead."),
        result("How much?", s.ANSWER, True, 0.4, shown="SAY: $120"),
        result("What colours?", s.ANSWER, True, 1.0, shown="SAY: white"),
        result("How heavy?", s.ANSWER, False, 0.3),
    ]
    s.report(results, "gemma3:12b on Ollama")
    out = capsys.readouterr().out
    assert "gemma3:12b on Ollama, 5 lines" in out
    assert "Answered when it should skip   1/2" in out
    assert "Skipped when it should answer  1/3" in out
    assert "Time to SKIP        median 0.25 s, slowest 0.30 s (2 lines)" in out
    assert "Time to first word  median 0.60 s, slowest 1.00 s (3 lines)" in out
    assert "answered, should skip [screen share] 'Let me share my screen.' -> 'SAY: Sure, go ahead.'" in out
    assert "skipped, should answer [question] 'How heavy?'" in out
    assert "'Hi'" not in out and "'How much?'" not in out


def test_report_without_mistakes_lists_no_wrong_lines(capsys):
    s.report([result("Hi", s.SKIP, False, 0.2), result("How much?", s.ANSWER, True, 0.4)])
    out = capsys.readouterr().out
    assert "0/1" in out and "Wrong" not in out


def test_report_says_none_when_no_line_was_skipped_or_answered(capsys):
    s.report([result("How much?", s.ANSWER, True, 0.4)])
    assert "Time to SKIP        none" in capsys.readouterr().out
    s.report([result("Hi", s.SKIP, False, 0.2)])
    assert "Time to first word  none" in capsys.readouterr().out


def test_a_long_reply_is_cut_in_the_list_of_wrong_lines(capsys):
    s.report([result("Hi", s.SKIP, True, 0.2, "greeting", "SAY: " + "word " * 40)])
    assert "..." in capsys.readouterr().out


# -- building the copilot, as the app does ------------------------------------------------------


def test_the_copilot_for_a_local_service_says_skip_by_itself_and_holds_only_the_document():
    prompt = material.as_prompt(material.load([DOCUMENT]))
    copilot = s.build_copilot(providers.provider("ollama"), None, "gemma3:12b", prompt)
    assert isinstance(copilot, OpenAICopilot) and copilot.gatekeeps
    assert copilot.model == "gemma3:12b"
    assert GATE in copilot.system and "Lumo L2" in copilot.system


# -- the command line ---------------------------------------------------------------------------


def test_main_prints_both_counts_and_exits_0(monkeypatch, capsys):
    monkeypatch.setattr(s, "build_copilot", lambda service, key, model, prompt: FakeCopilot(prompt, perfect))
    assert s.main(["--provider", "ollama", "--model", "gemma3:12b"]) == 0
    out = capsys.readouterr().out
    assert "gemma3:12b on Ollama" in out
    assert "Answered when it should skip   0/20" in out and "Skipped when it should answer  0/20" in out


def test_main_exits_0_even_when_the_model_makes_mistakes(monkeypatch, capsys):
    monkeypatch.setattr(s, "build_copilot", lambda service, key, model, prompt: FakeCopilot(prompt, answer_text))
    assert s.main(["--provider", "lm-studio", "--model", "x", "--runs", "2"]) == 0
    assert "Answered when it should skip   40/40" in capsys.readouterr().out


def test_main_needs_a_model(capsys):
    with pytest.raises(SystemExit) as stop:
        s.main(["--provider", "ollama"])
    assert stop.value.code == 2
    assert "--model" in capsys.readouterr().err


def test_main_refuses_anthropic_and_says_why(capsys):
    with pytest.raises(SystemExit) as stop:
        s.main(["--provider", "anthropic", "--model", "claude-haiku-4-5"])
    assert stop.value.code == 2
    assert "separate question check" in capsys.readouterr().err


def test_main_needs_a_key_for_a_service_that_requires_one(monkeypatch, capsys):
    monkeypatch.setattr(providers, "api_key", lambda provider_id: (None, ""))
    with pytest.raises(SystemExit) as stop:
        s.main(["--provider", "groq", "--model", "x"])
    assert stop.value.code == 2
    assert "no Groq key" in capsys.readouterr().err


def test_main_says_so_when_the_local_server_cannot_be_reached(monkeypatch, capsys):
    class Unreachable(FakeCopilot):
        def answer(self, question, before=""):
            raise openai.OpenAIError("Connection error.")
            yield  # a generator, like the real one

    monkeypatch.setattr(s, "build_copilot", lambda service, key, model, prompt: Unreachable(prompt, perfect))
    assert s.main(["--provider", "ollama", "--model", "gemma3:12b"]) == 2
    err = capsys.readouterr().err
    assert "Could not run gemma3:12b on Ollama" in err and "http://localhost:11434/v1" in err


# -- comparing several models -------------------------------------------------------------------


def fake_models(monkeypatch, replies):
    """build_copilot returns a FakeCopilot per model name; a reply of None means the model cannot be reached."""

    class Unreachable(FakeCopilot):
        def answer(self, question, before=""):
            raise openai.OpenAIError("model not found")
            yield  # a generator, like the real one

    def build(service, key, model, prompt):
        reply = replies[model]
        return Unreachable(prompt, perfect) if reply is None else FakeCopilot(prompt, reply)

    monkeypatch.setattr(s, "build_copilot", build)


def mute(question):
    return ["SKIP"]


def test_one_model_prints_the_report_and_no_table(monkeypatch, capsys):
    fake_models(monkeypatch, {"a": perfect})
    assert s.main(["--provider", "ollama", "--model", "a"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("a on Ollama · local, 40 lines\n\n")
    assert "Accuracy" not in out and "|" not in out


def test_several_model_names_are_read_in_order(monkeypatch, capsys):
    fake_models(monkeypatch, {"a": perfect, "b": perfect, "c": perfect})
    assert s.main(["--provider", "ollama", "--model", "c", "a", "b"]) == 0
    out = capsys.readouterr().out
    assert out.index("c on Ollama") < out.index("a on Ollama") < out.index("b on Ollama")
    assert out.index("| c |") < out.index("| a |") < out.index("| b |")


def test_three_models_make_three_rows_with_their_own_counts_and_accuracy(monkeypatch, capsys):
    fake_models(monkeypatch, {"good": perfect, "chatty": answer_text, "quiet": mute})
    assert s.main(["--provider", "ollama", "--model", "good", "chatty", "quiet"]) == 0
    out = capsys.readouterr().out
    assert out.count("Answered when it should skip   ") == 3  # the per-model reports are kept
    rows = {line.split("|")[1].strip(): [c.strip() for c in line.split("|")[2:-1]]
            for line in out.splitlines() if line.startswith("| ") and "Model" not in line}
    assert rows["good"][:3] == ["0/20", "0/20", "100.0%"]
    assert rows["chatty"][:3] == ["20/20", "0/20", "50.0%"]
    assert rows["quiet"][:3] == ["0/20", "20/20", "50.0%"]
    assert rows["quiet"][4] == "none" and rows["chatty"][3] == "none"  # never answered / never skipped


def test_the_table_has_the_six_columns_the_issue_names(monkeypatch, capsys):
    fake_models(monkeypatch, {"a": perfect, "b": perfect})
    s.main(["--model", "a", "b"])
    out = capsys.readouterr().out
    for column in s.COLUMNS:
        assert column in out
    assert len(s.COLUMNS) == 6


def test_a_model_that_cannot_be_reached_gets_a_failed_row_and_the_others_still_run(monkeypatch, capsys):
    fake_models(monkeypatch, {"a": perfect, "gone": None, "c": perfect})
    assert s.main(["--provider", "ollama", "--model", "a", "gone", "c"]) == 0
    captured = capsys.readouterr()
    assert "Could not run gone on Ollama · local" in captured.err
    assert "c on Ollama · local, 40 lines" in captured.out
    assert "| gone | failed: model not found | - | - | - | - |" in captured.out
    assert "| a | 0/20 | 0/20 | 100.0% |" in captured.out and "| c | 0/20 | 0/20 | 100.0% |" in captured.out


def test_when_every_model_fails_the_exit_status_is_2(monkeypatch, capsys):
    fake_models(monkeypatch, {"x": None, "y": None})
    assert s.main(["--provider", "ollama", "--model", "x", "y"]) == 2
    assert capsys.readouterr().out.count("| failed: model not found |") == 2


def test_runs_count_out_of_lines_times_runs_in_the_table(monkeypatch, capsys):
    fake_models(monkeypatch, {"a": answer_text, "b": perfect})
    s.main(["--model", "a", "b", "--runs", "2"])
    assert "| a | 40/40 | 0/40 | 50.0% |" in capsys.readouterr().out


def test_the_median_times_in_the_table_are_the_ones_the_report_prints():
    results = [result("Hi", s.SKIP, False, 0.2), result("Bye", s.SKIP, False, 0.3),
               result("How much?", s.ANSWER, True, 0.4), result("What colours?", s.ANSWER, True, 1.0)]
    assert s.summarise("m", results)[4:] == ["0.25 s", "0.70 s"]


def test_the_text_table_lines_up_its_columns():
    rows = [s.summarise("m", [result("Hi", s.SKIP, False, 0.2)]), s.failed_row("longer-name:4b", "boom")]
    lines = s.table(rows).splitlines()
    assert len(lines) == 4 and set(lines[1]) <= {"-", " "}
    start = lines[0].index("Answered when it should skip")
    assert all(line[start - 2:start] == "  " and line[start] != " " for line in lines[:1] + lines[2:])


def test_a_pipe_in_an_error_does_not_break_the_markdown_row():
    assert s.markdown_table([s.failed_row("m", "a | b\nc")]).splitlines()[2].count("|") == 7
