"""Tests for the PDF and Excel loaders in copilot/material.py (issue #49).

No network, no new dependencies: workbooks are built with openpyxl in
tmp_path, and pypdf.PdfReader is replaced with a fake.
"""

import openpyxl
import pypdf
import pytest

from copilot import material


def _load(path):
    """load() takes a list of paths and returns a list of Source objects."""
    sources = material.load([path])
    return "\n".join(s.text for s in sources)   # change .text to the real field name


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _make_workbook(path):
    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = "Sales"
    ws["A1"] = "apples"
    ws["B1"] = 3
    ws["A2"] = "pears"
    ws["B2"] = 2.5
    ws["C2"] = None  # empty cell, must be left out

    hidden = wb.create_sheet("Secret")
    hidden["A1"] = "top secret"
    hidden.sheet_state = "hidden"

    wb.save(path)
    return path


class FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self, *args, **kwargs):
        return self._text


def _fake_reader(page_texts):
    class FakeReader:
        is_encrypted = False

        def __init__(self, *args, **kwargs):
            self.pages = [FakePage(t) for t in page_texts]

    return FakeReader

# --------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------

def test_xlsx_visible_sheet_is_listed_with_cell_rows(tmp_path):
    path = _make_workbook(tmp_path / "book.xlsx")
    text = _load(path)

    assert "[sheet Sales]" in text
    assert "A1=apples | B1=3" in text
    assert "A2=pears | B2=2.5" in text


def test_xlsx_hidden_sheet_is_left_out(tmp_path):
    path = _make_workbook(tmp_path / "book.xlsx")
    text = _load(path)

    assert "[sheet Secret]" not in text
    assert "top secret" not in text


def test_xlsx_empty_cells_are_left_out(tmp_path):
    path = _make_workbook(tmp_path / "book.xlsx")
    text = _load(path)

    assert "C2" not in text


def test_xlsm_goes_through_excel_loader(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Macros"
    wb.active["A1"] = "hello"
    path = tmp_path / "book.xlsx"
    wb.save(path)
    # Same workbook content, but with the macro-enabled extension.
    xlsm = tmp_path / "book.xlsm"
    path.rename(xlsm)

    text = _load(xlsm)

    assert "[sheet Macros]" in text
    assert "A1=hello" in text


# --------------------------------------------------------------------------
# _cell number formatting
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        (3.14159, "3.1416"),
        (2.5, "2.5"),
        (1234567.8, "1,234,568"),
    ],
)
def test_cell_formats_floats(value, expected):
    assert material._cell(value) == expected


def test_cell_keeps_int_as_is():
    assert material._cell(7) in (7, "7")


def test_cell_keeps_string_as_is():
    assert material._cell("abc") == "abc"


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------

def test_pdf_pages_use_their_own_number(tmp_path, monkeypatch):
    monkeypatch.setattr(pypdf, "PdfReader", _fake_reader(["first", "second"]))
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"%PDF-fake")

    text = _load(path)

    assert "[page 1]" in text
    assert "first" in text
    assert "[page 2]" in text
    assert "second" in text


def test_pdf_empty_page_is_skipped_without_renumbering(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pypdf, "PdfReader", _fake_reader(["first", "", "third"])
    )
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"%PDF-fake")

    text = _load(path)

    assert "[page 1]" in text
    assert "[page 2]" not in text
    assert "[page 3]" in text  # keeps its real number
    assert "third" in text


def test_uppercase_pdf_extension_uses_pdf_loader(tmp_path, monkeypatch):
    monkeypatch.setattr(pypdf, "PdfReader", _fake_reader(["upper case ok"]))
    path = tmp_path / "DOC.PDF"
    path.write_bytes(b"%PDF-fake")

    text = _load(path)

    assert "[page 1]" in text
    assert "upper case ok" in text