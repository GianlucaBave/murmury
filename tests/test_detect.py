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
