import html
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QUrl

from copilot import app
from copilot.app import Window, answer_html, source_index, parse_source_link


def test_source_tag_links_when_only_one_document_is_loaded(tmp_path, monkeypatch):
    document = tmp_path / "plan.pdf"
    monkeypatch.setattr(app.theme, "palette", lambda: {
        "text": "#111", "tag_fg": "#333", "tag_bg": "#eee", "link": "#06c",
    })

    rendered = answer_html("- Revenue grew [page 12]", [document])

    assert 'href="murmury-source:0?tag=page%2012&amp;line=Revenue%20grew"' in rendered
    assert "&nbsp;page 12&nbsp;" in rendered


def test_source_tag_stays_plain_when_multiple_documents_make_it_ambiguous(tmp_path, monkeypatch):
    paths = [tmp_path / "plan.pdf", tmp_path / "forecast.xlsx"]
    monkeypatch.setattr(app.theme, "palette", lambda: {
        "text": "#111", "tag_fg": "#333", "tag_bg": "#eee", "link": "#06c",
    })

    rendered = answer_html("- Revenue grew [page 12]", paths)

    assert "href=" not in rendered
    assert "page 12" in rendered


def test_multi_document_source_resolves_only_an_explicit_filename(tmp_path):
    paths = [tmp_path / "plan.pdf", tmp_path / "forecast.xlsx"]

    assert source_index("forecast.xlsx sheet Summary!B4", paths) == 1
    assert source_index("plan.pdf page 12", paths) == 0
    assert source_index("page 12", paths) is None
    assert source_index("forecast.xlsx.evil page 12", paths) is None
    assert source_index("forecast.xlsx", paths) == 1


def test_multi_document_source_accepts_comma_after_filename():
    paths = [Path("plan.pdf"), Path("forecast.xlsx")]

    assert source_index("forecast.xlsx, sheet Summary", paths) == 1


def test_multi_document_source_handles_windows_path_separators():
    paths = [Path(r"C:\docs\plan.pdf"), Path(r"C:\docs\forecast.xlsx")]

    assert source_index("forecast.xlsx, sheet Summary", paths) == 1


def test_source_tag_with_explicit_filename_becomes_a_link(tmp_path, monkeypatch):
    paths = [tmp_path / "plan.pdf", tmp_path / "forecast.xlsx"]
    monkeypatch.setattr(app.theme, "palette", lambda: {
        "text": "#111", "tag_fg": "#333", "tag_bg": "#eee", "link": "#06c",
    })

    rendered = answer_html("- Revenue grew [forecast.xlsx sheet Summary!B4]", paths)

    assert 'href="murmury-source:1?tag=forecast.xlsx%20sheet%20Summary%21B4&amp;line=Revenue%20grew"' in rendered


def test_open_source_uses_local_file_url(tmp_path, monkeypatch):
    document = tmp_path / "plan.pdf"
    document.write_bytes(b"pdf")
    opened = []
    window = SimpleNamespace(source_paths=[document], set_status=lambda message: None)
    monkeypatch.setattr(app.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)

    Window.open_source(window, "murmury-source:0")

    assert opened == [QUrl.fromLocalFile(str(document))]


def test_open_source_ignores_invalid_or_out_of_range_links(tmp_path, monkeypatch):
    document = tmp_path / "plan.pdf"
    document.write_bytes(b"pdf")
    opened = []
    window = SimpleNamespace(source_paths=[document], set_status=lambda message: None)
    monkeypatch.setattr(app.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)

    Window.open_source(window, "https://example.com")
    Window.open_source(window, "murmury-source:4")

    assert opened == []


def test_open_source_reports_a_missing_document(tmp_path, monkeypatch):
    missing = tmp_path / "missing.pdf"
    statuses = []
    window = SimpleNamespace(source_paths=[missing], set_status=statuses.append)
    monkeypatch.setattr(app.QDesktopServices, "openUrl", lambda url: True)

    Window.open_source(window, "murmury-source:0")

    assert statuses == ["Source file is no longer available: missing.pdf"]


def test_open_source_reports_when_the_default_app_cannot_open_the_file(tmp_path, monkeypatch):
    document = tmp_path / "plan.pdf"
    document.write_bytes(b"pdf")
    statuses = []
    window = SimpleNamespace(source_paths=[document], set_status=statuses.append)
    monkeypatch.setattr(app.QDesktopServices, "openUrl", lambda url: False)

    Window.open_source(window, "murmury-source:0")

    assert statuses == ["Could not open plan.pdf"]


def test_source_link_carries_the_tag_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(app.theme, "palette", lambda: {
        "text": "#111", "tag_fg": "#333", "tag_bg": "#eee", "link": "#06c",
    })
    for tag in ["page 12", "sheet P&L", "notes.md#Pricing", 'the "base" case', "§4.2", "Q1+Q2"]:
        rendered = answer_html(f"- Revenue grew [{tag}]", [tmp_path / "plan.pdf"])
        href = html.unescape(re.search(r'href="([^"]+)"', rendered).group(1))
        assert parse_source_link(href) == (0, tag, "Revenue grew")


def test_parse_source_link_accepts_an_old_link_without_a_tag():
    assert parse_source_link("murmury-source:0") == (0, "", "")


def test_parse_source_link_rejects_links_that_are_not_ours():
    for link in ["https://example.com", "murmury-source:", "murmury-source:-1",
                 "murmury-source:0abc", "other-source:0?tag=page%2012"]:
        assert parse_source_link(link) is None

def test_open_source_never_takes_a_path_from_the_tag(tmp_path, monkeypatch):
    document = tmp_path / "plan.pdf"
    document.write_bytes(b"pdf")
    opened = []
    window = SimpleNamespace(source_paths=[document], set_status=lambda message: None)
    monkeypatch.setattr(app.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)

    Window.open_source(window, "murmury-source:0?tag=..%2F..%2Fetc%2Fpasswd")

    assert opened == [QUrl.fromLocalFile(str(document))]


def test_source_link_carries_the_fact_as_plain_text(tmp_path, monkeypatch):
    monkeypatch.setattr(app.theme, "palette", lambda: {
        "text": "#111", "tag_fg": "#333", "tag_bg": "#eee", "link": "#06c",
    })
    rendered = answer_html('- CAC: €3,900 in Year 1, "P&L" #2 + more [page 12]', [tmp_path / "plan.pdf"])
    href = html.unescape(re.search(r'href="([^"]+)"', rendered).group(1))

    assert parse_source_link(href) == (0, "page 12", 'CAC: €3,900 in Year 1, "P&L" #2 + more')
    assert "<b" not in href