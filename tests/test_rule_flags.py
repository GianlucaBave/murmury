# test_rule_flags.py
import pytest

from evals.run import rule_flags


def test_good_answer_clean():
    """A well-formed answer yields no flags."""
    text = (
        "SAY: Yes, the Pro plan is $120 a month.\n"
        "- Billed yearly, $1,440 in total [pricing.pdf]"
    )
    assert rule_flags(text, banned=[]) == []

def test_empty_answer_no_say():
    assert "no SAY first" in rule_flags("", banned=[])

def test_whitespace_only_no_say():
    assert "no SAY first" in rule_flags("   \n\n  ", banned=[])

def test_missing_say_first():
    text = "Hello there\n- Something [x]"
    assert "no SAY first" in rule_flags(text, banned=[])

def test_say_case_insensitive_prefix():
    text = "say: Yes, that works.\n- Billed yearly [pricing.pdf]"
    assert "no SAY first" not in rule_flags(text, banned=[])

def test_say_too_long_13_words():
    say = "one two three four five six seven eight nine ten eleven twelve thirteen"
    flags = rule_flags(f"SAY: {say}\n- ok [s]", banned=[])
    assert "SAY 13 words" in flags

def test_say_12_words_not_flagged():
    say = "one two three four five six seven eight nine ten eleven twelve"
    flags = rule_flags(f"SAY: {say}\n- ok [s]", banned=[])
    assert not any(f.startswith("SAY ") and f.endswith("words") for f in flags)

def test_say_opens_with_negation():
    flags = rule_flags("SAY: No, we don't offer that.\n- ok [s]", banned=[])
    assert "SAY opens with a negation" in flags

def test_say_negation_exception_not_flagged():
    flags = rule_flags("SAY: That is not in our plan, sorry.\n- ok [s]", banned=[])
    assert "SAY opens with a negation" not in flags

def test_say_negation_italian_exception_not_flagged():
    flags = rule_flags("SAY: Non è nel nostro piano, mi dispiace.\n- ok [s]", banned=[])
    assert "SAY opens with a negation" not in flags

def test_four_bullets_flagged():
    text = "SAY: Fine.\n- a [s]\n- b [s]\n- c [s]\n- d [s]"
    assert "4 lines" in rule_flags(text, banned=[])

def test_three_bullets_not_flagged():
    text = "SAY: Fine.\n- a [s]\n- b [s]\n- c [s]"
    assert not any(f.endswith(" lines") for f in rule_flags(text, banned=[]))

def test_four_bullets_allowed_with_bigger_max_lines():
    text = "SAY: Fine.\n- a [s]\n- b [s]\n- c [s]\n- d [s]"
    flags = rule_flags(text, banned=[], max_lines=5)
    assert "4 lines" not in flags

def test_stray_text_after_say():
    text = "SAY: Fine.\nThis is not a bullet [s]"
    flags = rule_flags(text, banned=[])
    assert any(f.startswith("stray text") for f in flags)


def test_bullet_lines_are_not_stray():
    text = "SAY: Fine.\n- a [s]\n* b [s]\n• c [s]"
    flags = rule_flags(text, banned=[])
    assert not any(f.startswith("stray text") for f in flags)

def test_bullet_without_source_flagged():
    flags = rule_flags("SAY: Fine.\n- Billed yearly", banned=[])
    assert any(f.startswith("no source:") for f in flags)


def test_not_in_plan_bullet_exempt_from_source():
    flags = rule_flags("SAY: Fine.\n- Not in plan", banned=[])
    assert not any(f.startswith("no source:") for f in flags)


def test_bullet_with_source_not_flagged():
    flags = rule_flags("SAY: Fine.\n- Billed yearly [pricing.pdf]", banned=[])
    assert not any(f.startswith("no source:") for f in flags)

def test_label_not_sentence_flagged():
    flags = rule_flags("SAY: Fine.\n- Price: $120 a month [s]", banned=[])
    assert any(f.startswith("label, not a sentence:") for f in flags)


def test_normal_sentence_not_flagged_as_label():
    flags = rule_flags("SAY: Fine.\n- Billed yearly at $1,440 [pricing.pdf]", banned=[])
    assert not any(f.startswith("label, not a sentence:") for f in flags)


def test_long_line_17_words_flagged():
    body = " ".join(["word"] * 17)
    flags = rule_flags(f"SAY: Fine.\n- {body} [s]", banned=[])
    assert any(f.startswith("long line:") for f in flags)


def test_long_line_16_words_not_flagged():
    body = " ".join(["word"] * 16)
    flags = rule_flags(f"SAY: Fine.\n- {body} [s]", banned=[])
    assert not any(f.startswith("long line:") for f in flags)


def test_long_line_source_bracket_not_counted():
    # 16 body words + [s] should still pass (bracket stripped before counting)
    body = " ".join(["word"] * 16)
    flags = rule_flags(f"SAY: Fine.\n- {body} [some/long/source.pdf]", banned=[])
    assert not any(f.startswith("long line:") for f in flags)


@pytest.mark.parametrize("word", ["Secret", "SECRET", "secret", "SeCrEt"])
def test_banned_word_case_insensitive(word):
    text = f"SAY: Fine.\n- Contains {word} here [s]"
    flags = rule_flags(text, banned=["secret"])
    assert "banned: secret" in flags


def test_banned_word_absent_not_flagged():
    flags = rule_flags("SAY: Fine.\n- All good [s]", banned=["secret"])
    assert not any(f.startswith("banned:") for f in flags)


def test_multiple_banned_words_all_reported():
    text = "SAY: Fine.\n- foo and bar [s]"
    flags = rule_flags(text, banned=["foo", "bar"])
    assert "banned: foo" in flags
    assert "banned: bar" in fla