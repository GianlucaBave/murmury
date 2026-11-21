import pytest

from evals.run import rule_flags

# ---------- Valid answer ----------


def test_valid_answer_returns_no_flags():
    answer = (
        "SAY: Yes, the Pro plan is $120 a month.\n"
        "- Billed yearly, $1,440 in total [pricing.pdf]"
    )
    assert rule_flags(answer, banned=[]) == []


def test_valid_answer_only_say_line():
    answer = "SAY: Yes, we offer that service."
    assert rule_flags(answer, banned=[]) == []


# ---------- Empty answer ----------


@pytest.mark.parametrize("empty_input", ["", "   ", "\n\n   \n"])
def test_empty_or_whitespace_answer_flags_no_say_first(empty_input):
    flags = rule_flags(empty_input, banned=[])
    assert "no SAY first" in flags


# ---------- Missing SAY first ----------


def test_answer_starting_directly_with_bullet():
    answer = "- Billed yearly, $1,440 in total [pricing.pdf]"
    flags = rule_flags(answer, banned=[])
    assert "no SAY first" in flags


def test_answer_with_ordinary_text_before_say():
    answer = "Here is the summary:\nSAY: Yes, we offer that.\n- Billed yearly [doc]"
    flags = rule_flags(answer, banned=[])
    assert "no SAY first" in flags


def test_answer_without_say_line():
    answer = "We offer that service.\n- Details on pricing [doc]"
    flags = rule_flags(answer, banned=[])
    assert "no SAY first" in flags


# ---------- SAY word-count limit ----------


def test_say_line_with_twelve_words_is_accepted():
    answer = (
        "SAY: one two three four five six seven eight nine ten eleven twelve\n"
        "- Fact [doc]"
    )
    assert rule_flags(answer, banned=[]) == []


def test_say_line_with_thirteen_words_is_flagged():
    answer = (
        "SAY: one two three four five six seven eight nine ten eleven twelve thirteen\n"
        "- Fact [doc]"
    )
    flags = rule_flags(answer, banned=[])
    assert "SAY 13 words" in flags


# ---------- Opening negation ----------


def test_say_opening_with_negation_is_flagged():
    answer = "SAY: No, we don't offer that.\n- Details [doc]"
    flags = rule_flags(answer, banned=[])
    assert "SAY opens with a negation" in flags


@pytest.mark.parametrize(
    "opening",
    [
        "No, that is unavailable.",
        "Not right now.",
        "We don't offer that tier.",
        "We dont support that feature.",
        "The plan does not include support.",
        "The plan doesn't include support.",
        "Non è disponibile per ora.",
        "Nessun piano lo prevede.",
    ],
)
def test_say_various_opening_negations_are_flagged(opening):
    answer = f"SAY: {opening}\n- Details [doc]"
    flags = rule_flags(answer, banned=[])
    assert "SAY opens with a negation" in flags


def test_say_internal_negation_not_flagged_as_opening_negation():
    answer = "SAY: That is not in our plan, sorry.\n- Details [doc]"
    assert "SAY opens with a negation" not in rule_flags(answer, banned=[])


@pytest.mark.parametrize(
    "say",
    [
        "That is not in our plan, sorry.",
        "that is not in our plan, but we have alternatives.",
        "Non è nel nostro piano, mi spiace.",
        "We offer that, but not the older version.",
        "The Pro plan does not include that tier.",
    ],
)
def test_say_allowed_or_internal_negation_not_flagged(say):
    answer = f"SAY: {say}\n- Details [doc]"
    assert "SAY opens with a negation" not in rule_flags(answer, banned=[])


# ---------- Maximum bullet-line limit ----------


def test_four_bullet_lines_flagged_under_default_max_lines():
    answer = (
        "SAY: Yes, the plan has these features.\n"
        "- First feature [doc]\n"
        "- Second feature [doc]\n"
        "- Third feature [doc]\n"
        "- Fourth feature [doc]"
    )
    flags = rule_flags(answer, banned=[])
    assert "4 lines" in flags


@pytest.mark.parametrize("allowed_max", [4, 5])
def test_four_bullet_lines_accepted_with_larger_max_lines(allowed_max):
    answer = (
        "SAY: Yes, the plan has these features.\n"
        "- First feature [doc]\n"
        "- Second feature [doc]\n"
        "- Third feature [doc]\n"
        "- Fourth feature [doc]"
    )
    assert rule_flags(answer, banned=[], max_lines=allowed_max) == []


# ---------- Stray text & bullet markers ----------


def test_stray_text_after_say_is_flagged():
    answer = (
        "SAY: Yes, we offer that.\n"
        "Here is some stray text without bullet\n"
        "- Valid fact [doc]"
    )
    flags = rule_flags(answer, banned=[])
    assert (
        "stray text (hidden in window): Here is some stray text without bullet" in flags
    )


@pytest.mark.parametrize("marker", ["-", "•", "*"])
def test_all_supported_bullet_markers_are_accepted(marker):
    answer = f"SAY: Yes, we offer that.\n{marker} Valid bullet line [doc]"
    assert rule_flags(answer, banned=[]) == []


# ---------- Missing source reference ----------


def test_bullet_without_source_is_flagged():
    answer = "SAY: Yes, we offer that.\n- Billed yearly, $1,440 in total"
    flags = rule_flags(answer, banned=[])
    assert "no source: - Billed yearly, $1,440 in total" in flags


@pytest.mark.parametrize(
    "bullet",
    [
        "- Not in plan",
        "• Not in plan",
        "* Not in plan",
        "- not in plan",
        "- Non nel piano",
    ],
)
def test_not_in_plan_exception_accepted_without_source(bullet):
    answer = f"SAY: That is not in our plan, sorry.\n{bullet}"
    assert rule_flags(answer, banned=[]) == []


def test_arbitrary_text_without_source_is_not_exempt():
    answer = "SAY: That is not in our plan, sorry.\n- Completely different text"
    flags = rule_flags(answer, banned=[])
    assert any(f.startswith("no source:") for f in flags)


# ---------- Label instead of a sentence ----------


def test_label_instead_of_sentence_is_flagged():
    answer = "SAY: Yes, we have details.\n- Price: $120 a month [s]"
    flags = rule_flags(answer, banned=[])
    assert "label, not a sentence: - Price: $120 a month [s]" in flags


def test_valid_sentence_with_source_is_not_flagged_as_label():
    answer = "SAY: Yes, we have details.\n- The price is $120 a month [s]"
    assert rule_flags(answer, banned=[]) == []


# ---------- Bullet word-count boundary ----------


def test_bullet_with_sixteen_words_is_accepted():
    answer = (
        "SAY: Yes.\n"
        "- one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen [doc]"
    )
    assert rule_flags(answer, banned=[]) == []


def test_bullet_with_seventeen_words_is_flagged_as_long_line():
    answer = (
        "SAY: Yes.\n"
        "- one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen seventeen [doc]"
    )
    flags = rule_flags(answer, banned=[])
    assert any(f.startswith("long line:") for f in flags)


def test_custom_max_words_boundary():
    # max_words = 10 -> slack is +2 -> limit is 12 words in body
    ok_answer = (
        "SAY: Yes.\n"
        "- one two three four five six seven eight nine ten eleven twelve [doc]"
    )
    assert rule_flags(ok_answer, banned=[], max_words=10) == []

    long_answer = (
        "SAY: Yes.\n"
        "- one two three four five six seven eight nine ten eleven twelve thirteen [doc]"
    )
    flags = rule_flags(long_answer, banned=[], max_words=10)
    assert any(f.startswith("long line:") for f in flags)


# ---------- Banned words ----------


@pytest.mark.parametrize(
    "variant",
    [
        "internal-codename",
        "INTERNAL-CODENAME",
        "Internal-Codename",
        "InTeRnAl-CoDeNaMe",
    ],
)
def test_banned_word_detected_case_insensitively(variant):
    answer = f"SAY: We use {variant} in production.\n- Details [doc]"
    flags = rule_flags(answer, banned=["internal-codename"])
    assert "banned: internal-codename" in flags


def test_unmentioned_banned_word_not_flagged():
    answer = "SAY: We use standard release in production.\n- Details [doc]"
    assert rule_flags(answer, banned=["internal-codename"]) == []


def test_multiple_banned_words_detected():
    answer = "SAY: Project uses alpha and beta components.\n- Details [doc]"
    flags = rule_flags(answer, banned=["alpha", "beta", "gamma"])
    assert "banned: alpha" in flags
    assert "banned: beta" in flags
    assert "banned: gamma" not in flags


# ---------- Additional edge and regression cases ----------


def test_multiple_violations_reported_together():
    answer = (
        "SAY: No, we don't offer that service because it is way too many words for a say line\n"
        "stray text commentary here\n"
        "- Price: $120 a month\n"
        "- Extra feature [doc]\n"
        "- Third feature [doc]\n"
        "- Fourth feature [doc]"
    )
    flags = rule_flags(answer, banned=["service"])
    assert "SAY 17 words" in flags
    assert "SAY opens with a negation" in flags
    assert "4 lines" in flags
    assert any(f.startswith("stray text (hidden in window):") for f in flags)
    assert any(f.startswith("label, not a sentence:") for f in flags)
    assert any(f.startswith("no source:") for f in flags)
    assert "banned: service" in flags


def test_whitespace_and_blank_lines_handled_properly():
    answer = (
        "\n   \n"
        "  SAY: Yes, the Pro plan is $120 a month.  \n"
        "\n"
        "  - Billed yearly, $1,440 in total [pricing.pdf]  \n"
        "\n   \n"
    )
    assert rule_flags(answer, banned=[]) == []


@pytest.mark.parametrize(
    "bad_source_line",
    [
        "- Feature without closing bracket [pricing.pdf",
        "- Feature with empty brackets []",
        "- Feature with trailing text after bracket [pricing.pdf] trailing",
    ],
)
def test_malformed_source_bracket_flagged_as_no_source(bad_source_line):
    answer = f"SAY: Yes, we offer that.\n{bad_source_line}"
    flags = rule_flags(answer, banned=[])
    assert any(f.startswith("no source:") for f in flags)
