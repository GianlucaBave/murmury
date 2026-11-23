import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from copilot.viewer import (after_name, best_block, find_section, headings, key_words, page_from_tag,
                            pdf_index, words)


def test_after_name_removes_the_file_name_and_its_separator():
    assert after_name("plan.pdf, page 12", "plan.pdf") == "page 12"
    assert after_name("plan.pdf page 12", "plan.pdf") == "page 12"
    assert after_name("PLAN.PDF: page 12", "plan.pdf") == "page 12"
    assert after_name("notes.md#Pricing", "notes.md") == "Pricing"


def test_after_name_is_none_when_the_tag_does_not_name_the_file():
    assert after_name("page 12", "plan.pdf") is None
    assert after_name("plan.pdf.evil page 12", "plan.pdf") is None


def test_page_from_tag_reads_the_ways_a_page_is_written():
    for text, page in [("page 12", 12), ("Page 12", 12), ("p. 12", 12), ("p.12", 12),
                       ("pp. 12-13", 12), ("pages 12–14", 12), ("§4.2, page 7", 7)]:
        assert page_from_tag(text) == page, text


def test_page_from_tag_does_not_mistake_other_numbers_for_pages():
    for text in ["Table 8", "Figure 6", "§4.2", "slide 3", "sheet Summary!B4", "sheet P&L", "step 3"]:
        assert page_from_tag(text) is None, text


def test_pdf_index_opens_the_cited_page_counted_from_zero():
    assert pdf_index("page 12", "plan.pdf", 40) == (11, None)
    assert pdf_index("plan.pdf, page 12", "plan.pdf", 40) == (11, None)


def test_pdf_index_accepts_the_first_and_last_page():
    assert pdf_index("page 1", "plan.pdf", 40) == (0, None)
    assert pdf_index("page 40", "plan.pdf", 40) == (39, None)


def test_pdf_index_falls_back_to_page_1_with_a_message():
    for tag in ["page 41", "page 0"]:
        index, message = pdf_index(tag, "plan.pdf", 40)
        assert index == 0 and message, tag


def test_pdf_index_without_a_page_number_opens_page_1_and_says_so():
    index, message = pdf_index("Table 8", "plan.pdf", 40)
    assert index == 0 and message


def test_pdf_index_with_no_tag_opens_page_1_quietly():
    assert pdf_index("", "plan.pdf", 40) == (0, None)


def test_pdf_index_ignores_a_page_number_inside_the_file_name():
    assert pdf_index("page 3 notes.pdf, page 12", "page 3 notes.pdf", 40) == (11, None)


NOTES = """# Plan

Intro text.

## Pricing history

We started at €10.

## Pricing

Three tiers: €20, €50, €90.

### Enterprise

Custom contracts.

## 4.2 Go-to-market

Founders sell first.

~~~
# not a heading
~~~

## Team

Two founders.
"""


def shown(tag):
    start, end, message = find_section(tag, "notes.md", NOTES)
    return NOTES[start:end], message



def test_words_keeps_section_numbers_whole():
    assert words("§4.2 Go-to-market") == ["4.2", "go", "to", "market"]
    assert words("## Pricing") == ["pricing"]


def test_headings_skips_lines_inside_code_blocks():
    titles = [title for _, _, title in headings(NOTES)]
    assert titles == ["Plan", "Pricing history", "Pricing", "Enterprise", "4.2 Go-to-market", "Team"]


def test_find_section_shows_the_heading_and_its_subsections():
    text, message = shown("notes.md#Pricing")
    assert text.startswith("## Pricing\n")
    assert "Custom contracts." in text
    assert "Pricing history" not in text and "4.2 Go-to-market" not in text
    assert message is None


def test_find_section_finds_a_numbered_heading_from_its_number():
    text, _ = shown("§4.2")
    assert text.startswith("## 4.2 Go-to-market")
    assert "Founders sell first." in text


def test_find_section_of_a_subsection_stops_at_the_next_heading_above_it():
    text, _ = shown("Enterprise")
    assert text.startswith("### Enterprise")
    assert "4.2" not in text


def test_find_section_of_the_last_heading_runs_to_the_end():
    text, _ = shown("Team")
    assert text == "## Team\n\nTwo founders.\n"


def test_find_section_falls_back_to_the_start_with_a_message():
    assert find_section("Roadmap", "notes.md", NOTES)[:2] == (0, len(NOTES))
    assert find_section("Roadmap", "notes.md", NOTES)[2]


def test_find_section_with_no_tag_shows_the_start_quietly():
    assert find_section("", "notes.md", NOTES) == (0, len(NOTES), None)


def test_find_section_never_jumps_into_a_code_block():
    assert find_section("not a heading", "notes.md", NOTES)[2]


def test_find_section_does_not_confuse_4_with_4_2():
    assert find_section("§4", "notes.md", NOTES)[2]


def highlighted(fact, tag=""):
    start, end, _ = find_section(tag, "notes.md", NOTES)
    found = best_block(fact, NOTES, start, end)
    return NOTES[found[0]:found[1]] if found else None


def test_key_words_keeps_numbers_and_acronyms_and_drops_little_words():
    assert key_words("We cut CAC to €3,900 in Year 1") == ["cut", "cac", "3", "900", "year", "1"]


def test_best_block_highlights_the_line_a_fact_comes_from():
    assert highlighted("Our three tiers cost €20, €50 and €90 a month", "Pricing") == "Three tiers: €20, €50, €90."


def test_best_block_picks_the_line_that_shares_the_most():
    assert highlighted("Custom contracts for enterprise", "Pricing") == "Custom contracts."


def test_best_block_stays_inside_the_section():
    assert highlighted("We started at €10 a seat", "Pricing") is None
    assert highlighted("We started at €10 a seat") == "We started at €10."


def test_best_block_highlights_nothing_when_few_words_are_shared():
    assert highlighted("Three founders run sales") is None


def test_best_block_highlights_nothing_for_an_answer_in_another_language():
    assert highlighted("Abbiamo tre fasce di prezzo") is None


def test_best_block_highlights_nothing_for_an_empty_fact():
    assert highlighted("") is None
    assert highlighted("We do it") is None