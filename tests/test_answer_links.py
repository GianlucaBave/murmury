import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from copilot.app import Bridge, Window, answer_html, resolve_source_target


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def test_resolve_source_target_single_document():
    doc = Path("/tmp/single_doc.pdf")
    assert resolve_source_target("page 12", [doc]) == doc
    assert resolve_source_target("slide 3", [doc]) == doc
    assert resolve_source_target("anything", [doc]) == doc


def test_resolve_source_target_multi_document():
    doc1 = Path("/tmp/annual_report.pdf")
    doc2 = Path("/tmp/financial_model.xlsx")
    docs = [doc1, doc2]

    # Named by filename or stem
    assert resolve_source_target("annual_report.pdf page 3", docs) == doc1
    assert resolve_source_target("annual_report §2", docs) == doc1
    assert resolve_source_target("financial_model.xlsx!B4", docs) == doc2
    assert resolve_source_target("financial_model", docs) == doc2

    # Ambiguous tag with multiple documents
    assert resolve_source_target("page 3", docs) is None
    assert resolve_source_target("table 1", docs) is None


def test_resolve_source_target_empty_docs():
    assert resolve_source_target("page 12", []) is None


def test_answer_html_single_doc_makes_tag_clickable():
    doc = Path("/path/to/my_notes.md")
    html_out = answer_html("- Revenue grew 15% [page 4]", docs=[doc])
    expected_url = QUrl.fromLocalFile(str(doc.resolve())).toString()

    assert f'<a href="{expected_url}"' in html_out
    assert "page 4" in html_out


def test_answer_html_multi_doc_links_only_matching():
    doc1 = Path("/path/to/deck.pptx")
    doc2 = Path("/path/to/budget.xlsx")
    docs = [doc1, doc2]

    # Matching doc2
    html_out = answer_html("- Runway is 18m [budget.xlsx]", docs=docs)
    expected_url = QUrl.fromLocalFile(str(doc2.resolve())).toString()
    assert f'<a href="{expected_url}"' in html_out

    # Ambiguous tag with multiple docs
    html_ambiguous = answer_html("- Runway is 18m [slide 4]", docs=docs)
    assert "<a href=" not in html_ambiguous
    assert "slide 4" in html_ambiguous


def test_window_open_link_invokes_desktop_services(application, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url))

    bridge = Bridge()
    doc = Path("/path/to/my_deck.pptx")
    window = Window(bridge, lambda _: None, docs=[doc])

    test_url = QUrl.fromLocalFile(str(doc.resolve())).toString()
    window.open_link(test_url)

    assert len(opened) == 1
    assert opened[0].toString() == test_url

    window.close()
    window.deleteLater()
    application.processEvents()


def test_window_card_answer_links_source_and_activates(application, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url))

    bridge = Bridge()
    doc = Path("/path/to/test_plan.pdf")
    window = Window(bridge, lambda _: None, docs=[doc])

    bridge.card.emit(1, "What is our runway?")
    bridge.answer.emit(1, "SAY: 15 months.\n- About 15 months [page 3]")

    answer_label = window.cards[1][2]
    expected_url = QUrl.fromLocalFile(str(doc.resolve())).toString()
    assert f'<a href="{expected_url}"' in answer_label.text()

    # Trigger linkActivated signal
    answer_label.linkActivated.emit(expected_url)
    assert len(opened) == 1
    assert opened[0].toString() == expected_url

    window.close()
    window.deleteLater()
    application.processEvents()
