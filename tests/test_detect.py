"""Tests for evals/detect.py: the question detectors and how they are scored."""

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
