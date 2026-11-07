import re

import pytest

from copilot import app
from copilot.app import answer_html, card_lines


@pytest.fixture(autouse=True)
def bullet_cards_of_three_facts(monkeypatch):
    """Both are set from the answer style at start: fixed here so no test depends on the defaults."""
    monkeypatch.setattr(app, "MAX_LINES", 3)
    monkeypatch.setattr(app, "FORMAT", "talking")


def bold(card: str) -> list[str]:
    return [text.strip() for text in re.findall(r"<b\b[^>]*>(.*?)</b>", card)]


def source_tags(card: str) -> list[str]:
    return re.findall(r"<span\b[^>]*>&nbsp;(.*?)&nbsp;</span>", card)


def visible(card: str) -> str:
    return re.sub(r"<[^>]+>", "", card)


def test_the_say_line_is_kept_with_its_facts():
    assert card_lines("SAY: We grew.\n- Revenue up 5%") == ["SAY: We grew.", "- Revenue up 5%"]


@pytest.mark.parametrize("second", ["SAY: Second.", "say: Second."])
def test_only_the_first_say_line_is_used(second):
    text = f"SAY: First.\n- A fact\n{second}\n- Another fact"
    assert card_lines(text) == ["SAY: First.", "- A fact", "- Another fact"]
    assert "Second" not in answer_html(text)


@pytest.mark.parametrize("limit", [1, 2, 5])
def test_facts_beyond_max_lines_are_dropped(monkeypatch, limit):
    monkeypatch.setattr(app, "MAX_LINES", limit)
    facts = [f"- Fact {n}" for n in range(limit + 2)]
    assert card_lines("\n".join(["SAY: Yes.", *facts])) == ["SAY: Yes.", *facts[:limit]]


def test_without_a_say_line_the_first_bullet_takes_its_place():
    facts = [f"- Fact {n}" for n in range(6)]
    assert card_lines("\n".join(facts)) == facts[:4]


def test_text_that_is_neither_say_nor_a_bullet_is_ignored():
    text = "Sure, here is the answer.\n\nSAY: Yes.\nFrom the deck:\n- A fact\nHope that helps!"
    assert card_lines(text) == ["SAY: Yes.", "- A fact"]
    assert visible(answer_html(text)) == "Yes.A fact"


@pytest.mark.parametrize("line", ["- A fact", "• A fact", "* A fact", "   - A fact   "])
def test_every_bullet_mark_counts_as_a_fact(line):
    assert card_lines(line) == [line.strip()]
    assert visible(answer_html(line)) == "A fact"


def test_the_say_line_is_bold_without_its_prefix():
    card = answer_html("SAY: We grew.")
    assert re.fullmatch(r'<p style="[^"]*font-weight:600;[^"]*">We grew\.</p>', card)


def test_the_source_is_shown_as_a_tag_and_taken_out_of_the_fact():
    card = answer_html("- Revenue grew [page 12]")
    assert source_tags(card) == ["page 12"]
    assert "[page 12]" not in card
    assert "Revenue grew" in card


@pytest.mark.parametrize("line", ["- Revenue grew", "- See [page 12] for more"])
def test_no_tag_without_a_source_at_the_end_of_the_line(line):
    assert source_tags(answer_html(line)) == []


def test_the_number_in_a_source_is_not_the_number_of_the_fact():
    assert bold(answer_html("- Revenue grew [page 12]")) == []


def test_only_the_first_number_of_a_fact_is_bold():
    assert bold(answer_html("- Up 12% to 30 units in 2024")) == ["12%"]


def test_each_fact_has_its_own_bold_number():
    assert bold(answer_html("- Up 12%\n- Down 7%")) == ["12%", "7%"]


@pytest.mark.parametrize("number", ["7", "1,200", "3.5", "12%", "2x", "2×", "€5m", "$3bn", "£40k",
                                    "5 million", "5 billion"])
def test_a_number_is_bold_with_its_currency_and_unit(number):
    assert bold(answer_html(f"- Reached {number} today")) == [number]


@pytest.mark.parametrize("line, number", [("- Took 3 months", "3"), ("- Ran 12 km", "12"),
                                          ("- Sold 4 bikes", "4"), ("- Saw 6 xrays", "6")])
def test_a_word_after_a_number_is_not_cut_at_a_letter_that_looks_like_a_unit(line, number):
    card = answer_html(line)
    assert bold(card) == [number]
    assert visible(card) == line[2:]


def test_a_label_is_bold_and_its_digits_are_not_the_number():
    assert bold(answer_html("- Revenue 2024: 7 dollars")) == ["Revenue 2024:", "7"]


def test_an_apostrophe_does_not_put_digits_in_the_fact():
    assert bold(answer_html("- It's the client's 5th order")) == ["5"]


@pytest.mark.parametrize("line, escaped", [
    ("SAY: <script>alert('x')</script>", "&lt;script&gt;alert('x')&lt;/script&gt;"),
    ("- <img src=x onerror=y> is new", "&lt;img src=x onerror=y&gt; is new"),
    ("- Costs: <b>high</b>", "&lt;b&gt;high&lt;/b&gt;"),
    ("- R&D: flat", "R&amp;D:"),
    ("- Flat [<i>page</i>]", "&lt;i&gt;page&lt;/i&gt;"),
])
def test_html_in_the_answer_is_escaped(line, escaped):
    card = answer_html(line)
    assert escaped in card
    assert not re.search(r"<(script|img|i)\b", card)
    assert "<b>" not in card


def test_escaping_leaves_the_number_of_the_fact_bold():
    card = answer_html("- <em>Up</em> 12% & rising")
    assert "&lt;em&gt;Up&lt;/em&gt;" in card and "&amp; rising" in card
    assert bold(card) == ["12%"]
