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


def test_a_row_has_the_name_the_counts_the_accuracy_and_the_time():
    lines = [line("Can you hear me okay?", SKIP, "audio check"),
             line("Tell me the price.", ANSWER, "request"),
             line("Hello everyone.", SKIP, "greeting")]
    result = detect.Score("rules", "development", lines, [lines[0]], [lines[1]], 12.34)
    assert detect.row(result) == ["rules", "development (3)", "1/2", "1/1", "33.3%", "12.3 us"]


def test_the_accuracy_of_no_lines_is_zero():
    assert detect.Score("rules", "empty", [], [], [], 0.0).accuracy == 0.0


def test_the_table_lines_up_the_columns_under_the_header_and_a_dashed_rule():
    rows = [["rules", "development (2)", "1/1", "0/1", "50.0%", "1.0 us"],
            ["question mark", "held-out (3)", "0/2", "1/1", "66.7%", "9.5 us"]]
    lines = detect.table(rows).splitlines()
    assert len(lines) == len(rows) + 2
    starts = [lines[0].index(name) for name in detect.COLUMNS]
    assert all(dash == "-" for start in starts for dash in lines[1][start:start + 1])
    assert set(lines[1]) <= {"-", " "}
    for name, start in zip(detect.COLUMNS, starts):
        assert lines[0][start:].startswith(name)
    for row, text in zip(rows, lines[2:]):
        assert all(text[start:].startswith(cell) for start, cell in zip(starts, row))


def test_the_markdown_table_has_a_separator_and_the_same_pipes_on_every_line():
    rows = [["rules", "development (2)", "1/1", "0/1", "50.0%", "1.0 us"]]
    lines = detect.markdown_table(rows).splitlines()
    assert lines[0] == "| " + " | ".join(detect.COLUMNS) + " |"
    assert lines[1].startswith("|") and set(lines[1]) <= {"|", "-"}
    assert len(lines) == len(rows) + 2
    assert all(text.count("|") == len(detect.COLUMNS) + 1 for text in lines)


def test_wrong_lines_lists_both_mistakes_with_their_kind():
    lines = [line("Can you hear me okay?", SKIP, "audio check"),
             line("Tell me the price.", ANSWER, "request")]
    result = detect.Score("question mark", "tiny", lines, [lines[0]], [lines[1]], 0.0)
    assert detect.wrong_lines(result).splitlines() == [
        "question mark, tiny lines, wrong:",
        "  answered, should skip [audio check] 'Can you hear me okay?'",
        "  skipped, should answer [request] 'Tell me the price.'",
    ]


def test_wrong_lines_with_no_mistakes_is_just_the_header():
    lines = [line("How much is it?")]
    result = detect.Score("question mark", "tiny", lines, [], [], 0.0)
    assert detect.wrong_lines(result).splitlines() == ["question mark, tiny lines, wrong:"]


def test_the_time_per_line_calls_the_detector_passes_times_repeats_times_lines():
    calls = []
    def detector(entry):
        calls.append(entry.text)
        return True
    lines = [line("How much is it?"), line("Is it dimmable?")]
    seconds = detect.microseconds_per_line(detector, lines, passes=3, repeats=4)
    assert len(calls) == 3 * 4 * len(lines)
    assert seconds >= 0


def test_the_time_per_line_of_no_lines_is_zero_and_calls_nothing():
    calls = []
    def detector(entry):
        calls.append(entry.text)
        return True
    assert detect.microseconds_per_line(detector, []) == 0.0
    assert calls == []
