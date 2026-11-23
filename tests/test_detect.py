"""Tests for evals/detect.py: the question detectors and how they are scored."""

import pytest

from evals import detect
from evals.skip import ANSWER, SKIP, Line, load


def line(text, expect=ANSWER, kind="question", before=""):
    return Line(text, expect, kind, before)


def test_question_mark_rule_looks_only_at_the_end_of_the_line():
    assert detect.question_mark(line("How much does it cost?"))
    assert detect.question_mark(line("  and the height?  "))
    assert not detect.question_mark(line("Tell me the price."))
    assert not detect.question_mark(line(""))


def test_both_mistakes_are_listed_separately():
    lines = [line("Can you hear me okay?", SKIP, "audio check"),
             line("Tell me the price.", ANSWER, "request"),
             line("How much is it?"),
             line("Hello everyone.", SKIP, "greeting")]
    false_answers, false_skips = detect.run(detect.question_mark, lines)
    assert [entry.text for entry in false_answers] == ["Can you hear me okay?"]
    assert [entry.text for entry in false_skips] == ["Tell me the price."]


def test_the_score_counts_the_mistakes_and_the_accuracy():
    lines = [line("Can you hear me okay?", SKIP, "audio check"),
             line("Tell me the price.", ANSWER, "request"),
             line("How much is it?"),
             line("Hello everyone.", SKIP, "greeting")]
    result = detect.score("question mark", detect.question_mark, "tiny", lines)
    assert (len(result.false_answers), len(result.false_skips)) == (1, 1)
    assert result.accuracy == 50.0
    assert result.microseconds >= 0


def test_the_held_out_lines_share_nothing_with_the_development_lines():
    development = {entry.text for entry in load(detect.LINES)[1]}
    held_out = {entry.text for entry in load(detect.HELDOUT)[1]}
    assert development and held_out
    assert not development & held_out


def test_both_files_have_lines_to_answer_and_lines_to_skip():
    for path in (detect.LINES, detect.HELDOUT):
        assert {entry.expect for entry in load(path)[1]} == {ANSWER, SKIP}


def test_held_out_misses_are_listed_only_when_asked(capsys):
    held_out = load(detect.HELDOUT)[1]
    false_answers, false_skips = detect.run(detect.question_mark, held_out)
    missed = [entry.text for entry in false_answers + false_skips]
    assert missed
    detect.main([])
    shown = capsys.readouterr().out
    assert not any(text in shown for text in missed)
    detect.main(["--show-heldout-errors"])
    shown = capsys.readouterr().out
    assert all(text in shown for text in missed)


@pytest.mark.parametrize("text, answered", [
    ("How much does the lamp cost?", True),
    ("and the height?", True),
    ("Tell me what the lamp is made for.", True),
    ("I\u2019d like to know how long the cable is.", True),
    ("Can you hear me okay?", False),
    ("How's the weather over there?", False),
    ("Let me share my screen.", False),
    ("Give me a moment, I'm opening the file.", False),
    ("Thanks, that's helpful.", False),
    ("", False),
])
def test_rules_answer_questions_and_requests_but_not_call_chatter(text, answered):
    assert detect.rules(line(text)) is answered


TOY = [
    ("What is the price of the lamp?", detect.ANSWER),
    ("How tall is it?", detect.ANSWER),
    ("Is it dimmable?", detect.ANSWER),
    ("What colours does it come in?", detect.ANSWER),
    ("Thanks, that is all.", detect.SKIP),
    ("Hello everyone, welcome.", detect.SKIP),
    ("Let me share my screen.", detect.SKIP),
    ("Okay, great, perfect.", detect.SKIP),
]


def test_features_are_repeatable_and_mark_a_final_question_mark():
    vector = detect.features("Is it dimmable?")
    assert vector.shape == (detect.BUCKETS + 1,)
    assert (vector == detect.features("Is it dimmable?")).all()
    assert vector[-1] == 1.0
    assert detect.features("Is it dimmable.")[-1] == 0.0
    assert abs(float((vector[:-1] ** 2).sum()) - 1.0) < 1e-9


def test_training_is_repeatable_and_separates_a_toy_set():
    lines = [line(text, expect) for text, expect in TOY]
    weights = detect.train(lines)
    assert (weights == detect.train(lines)).all()
    classify = detect.classifier(weights)
    assert [classify(item) for item in lines] == [item.expect == detect.ANSWER for item in lines]


def test_score_accuracy_is_zero_for_empty_lines():
    empty = detect.Score("rules", "empty", [], [], [], 0.0)
    assert empty.accuracy == 0.0


def test_row_formats_detector_counts_accuracy_and_time():
    skip_1 = line("Can you hear me?", SKIP, "audio check")
    skip_2 = line("Hello everyone.", SKIP, "greeting")
    ans_1 = line("How much is it?", ANSWER, "price")
    ans_2 = line("Tell me the price.", ANSWER, "request")
    result = detect.Score(
        "rules",
        "development",
        [skip_1, skip_2, ans_1, ans_2],
        false_answers=[skip_1],
        false_skips=[ans_2],
        microseconds=1.24,
    )
    assert detect.row(result) == ["rules", "development (4)", "1/2", "1/2", "50.0%", "1.2 us"]


def test_table_and_markdown_table_format_columns():
    rows = [
        ["rules", "development (2)", "0/1", "0/1", "100.0%", "1.2 us"],
        ["question mark", "held-out (20)", "1/10", "2/10", "85.0%", "0.4 us"],
    ]
    plain = detect.table(rows).splitlines()
    assert len(plain) == 4
    assert all(set(ch for ch in part) == {"-"} for part in plain[1].split("  "))
    assert len(plain[0]) <= len(plain[1])
    assert plain[2].index("development (2)") == plain[3].index("held-out (20)")

    md = detect.markdown_table(rows).splitlines()
    assert len(md) == 4
    assert "---" in md[1]
    pipe_counts = {row_str.count("|") for row_str in md}
    assert len(pipe_counts) == 1


def test_wrong_lines_lists_misses_or_header_only():
    skip_line = line("Can you hear me?", SKIP, "audio check")
    ans_line = line("Tell me the price.", ANSWER, "request")
    clean = detect.Score("rules", "dev", [skip_line, ans_line], [], [], 0.5)
    assert detect.wrong_lines(clean) == "rules, dev lines, wrong:"

    with_misses = detect.Score("rules", "dev", [skip_line, ans_line], [skip_line], [ans_line], 0.5)
    text = detect.wrong_lines(with_misses)
    assert text.splitlines() == [
        "rules, dev lines, wrong:",
        "  answered, should skip [audio check] 'Can you hear me?'",
        "  skipped, should answer [request] 'Tell me the price.'",
    ]


def test_microseconds_per_line_call_count_and_empty():
    calls = 0

    def counting_detector(_line: Line) -> bool:
        nonlocal calls
        calls += 1
        return False

    assert detect.microseconds_per_line(counting_detector, []) == 0.0
    assert calls == 0

    sample = [line("One?"), line("Two."), line("Three?")]
    elapsed = detect.microseconds_per_line(counting_detector, sample, passes=3, repeats=4)
    assert calls == 3 * 4 * len(sample)
    assert elapsed >= 0.0
