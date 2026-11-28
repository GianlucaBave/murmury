import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pathlib import Path

from PySide6.QtWidgets import QApplication

from copilot import app
from copilot.app import answer_html, source_index
from copilot.material import Source
from copilot.sources import tag_exists

APP = QApplication.instance() or QApplication([])
PALETTE = {"text": "#111", "tag_fg": "#333", "tag_bg": "#eee", "link": "#06c"}

PDF = Source("plan.pdf", "pdf", "[page 1]\nHello\n\n[page 2]\nWorld")
MARKDOWN = Source("q3-review.md", "text",
                  "# Northwind Analytics: Q3 2026 business review\n\n## Revenue by segment (EUR million)\nx\n\n## Hiring\ny")
SHEET = Source("model.xlsx", "xlsx", "[sheet Sales]\nA1=Region | B1=Revenue\nA2=EU | B2=10\n\n[sheet Costs]\nA1=Item | B1=Cost")
SLIDES = Source("deck.pptx", "pptx", "[slide 1]\nTitle\n\n[slide 2]\nMore")


@pytest.mark.parametrize("tag", ["page 2", "p. 2", "plan.pdf, page 2", "plan.pdf", "Plan.PDF, page 1"])
def test_a_pdf_tag_for_an_existing_page_or_the_file_passes(tag):
    assert tag_exists(tag, PDF)


@pytest.mark.parametrize("tag", ["page 3", "plan.pdf, page 9", "?2.1", "Table 1", "source", "", "other.pdf, page 1"])
def test_a_pdf_tag_for_a_missing_place_or_another_file_fails(tag):
    assert not tag_exists(tag, PDF)


@pytest.mark.parametrize("tag", ["Hiring", "hiring", "q3-review.md, Hiring", "Revenue by segment (EUR million)",
                                 "revenue by segment (eur million)", "q3-review.md"])
def test_a_markdown_tag_for_an_existing_heading_or_the_file_passes(tag):
    assert tag_exists(tag, MARKDOWN)


@pytest.mark.parametrize("tag", ["?2.1", "?3.1", "Table 1", "Payroll", "page 1", "source", ""])
def test_a_markdown_tag_for_a_missing_place_fails(tag):
    assert not tag_exists(tag, MARKDOWN)


@pytest.mark.parametrize("tag", ["Sales!B2", "sales!b2", "B2", "B1", "sheet Sales", "model.xlsx, Costs!B1"])
def test_a_spreadsheet_tag_for_an_existing_sheet_or_cell_passes(tag):
    assert tag_exists(tag, SHEET)


@pytest.mark.parametrize("tag", ["Sales!B9", "Costs!B2", "B9", "sheet Nope", "page 1"])
def test_a_spreadsheet_tag_for_a_missing_sheet_or_cell_fails(tag):
    assert not tag_exists(tag, SHEET)


@pytest.mark.parametrize("tag, expected", [("slide 2", True), ("deck.pptx, slide 1", True), ("slide 3", False), ("page 1", False)])
def test_a_slide_tag_is_checked_against_the_slide_markers(tag, expected):
    assert tag_exists(tag, SLIDES) is expected


def test_an_escaped_file_name_in_the_tag_still_matches():
    source = Source('Offer "final".pdf', "pdf", "[page 1]\nx")
    assert tag_exists("Offer &quot;final&quot;.pdf, page 1", source)
    assert not tag_exists("Offer &quot;final&quot;.pdf, page 2", source)


def _html(text, paths, sources, monkeypatch):
    monkeypatch.setattr(app.theme, "palette", lambda: PALETTE)
    return answer_html(text, paths, sources)


def test_a_tag_for_a_missing_place_is_plain_text_even_with_one_document(monkeypatch):
    rendered = _html("- Revenue grew [?2.1]", [Path("q3-review.md")], [MARKDOWN], monkeypatch)
    assert "href=" not in rendered
    assert "?2.1" in rendered


def test_a_tag_for_an_existing_heading_is_clickable(monkeypatch):
    rendered = _html("- We hire two people [Hiring]", [Path("q3-review.md")], [MARKDOWN], monkeypatch)
    assert 'href="murmury-source:0?tag=Hiring' in rendered


def test_without_the_loaded_documents_a_tag_is_accepted_as_before(monkeypatch):
    rendered = _html("- Revenue grew [?2.1]", [Path("q3-review.md")], None, monkeypatch)
    assert 'href="murmury-source:0?' in rendered


def test_with_several_documents_the_file_and_the_place_must_both_check_out(monkeypatch):
    paths, sources = [Path("plan.pdf"), Path("model.xlsx")], [PDF, SHEET]
    assert 'href="murmury-source:0?' in _html("- a [plan.pdf, page 2]", paths, sources, monkeypatch)
    assert 'href="murmury-source:1?' in _html("- a [model.xlsx, Sales!B2]", paths, sources, monkeypatch)
    assert "href=" not in _html("- a [plan.pdf, page 9]", paths, sources, monkeypatch)
    assert "href=" not in _html("- a [page 2]", paths, sources, monkeypatch)


def test_a_tag_naming_another_file_is_plain_text_even_with_one_document(monkeypatch):
    assert "href=" not in _html("- a [other.pdf, page 1]", [Path("plan.pdf")], [PDF], monkeypatch)


def test_source_index_checks_the_place_only_once_the_documents_are_loaded():
    assert source_index("page 2", [Path("plan.pdf")], [PDF]) == 0
    assert source_index("page 9", [Path("plan.pdf")], [PDF]) is None
    assert source_index("page 9", [Path("plan.pdf")], []) == 0
