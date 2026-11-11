from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from pypdf import PdfWriter
from copilot.material import as_prompt, load


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def _archive(path: Path, members: dict[str, str]) -> None:
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)


def test_docx_keeps_paragraphs_and_tables_in_document_order(tmp_path):
    path = tmp_path / "brief.docx"
    _archive(
        path,
        {
            "word/document.xml": f"""<w:document xmlns:w="{W}"><w:body>
              <w:p><w:r><w:t>Opening</w:t></w:r></w:p>
              <w:tbl><w:tr>
                <w:tc><w:p><w:r><w:t>Metric</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>Value</w:t></w:r></w:p></w:tc>
              </w:tr></w:tbl>
              <w:p><w:r><w:t>Conclusion</w:t></w:r></w:p>
            </w:body></w:document>""",
        },
    )

    [source] = load([path])

    assert source.kind == "docx"
    assert source.text == "Opening\n\nMetric | Value\n\nConclusion"
    assert as_prompt(load([path])) == as_prompt(load([path]))


def test_pptx_uses_declared_slide_order_and_includes_notes(tmp_path):
    path = tmp_path / "board.pptx"
    slide = lambda text: (
        f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:txBody>'
        f"<a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )
    notes = f"""<p:notes xmlns:p="{P}" xmlns:a="{A}"><p:cSld>
      <p:sp><p:nvSpPr><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr><p:txBody>
        <a:p><a:r><a:t>Confirm the target</a:t></a:r></a:p>
      </p:txBody></p:sp>
      <p:sp><p:nvSpPr><p:nvPr><p:ph type="sldNum"/></p:nvPr></p:nvSpPr><p:txBody>
        <a:p><a:r><a:t>99</a:t></a:r></a:p>
      </p:txBody></p:sp>
    </p:cSld></p:notes>"""
    _archive(
        path,
        {
            "ppt/presentation.xml": f"""<p:presentation xmlns:p="{P}" xmlns:r="{R}">
              <p:sldIdLst><p:sldId id="2" r:id="rId2"/><p:sldId id="1" r:id="rId1"/></p:sldIdLst>
            </p:presentation>""",
            "ppt/_rels/presentation.xml.rels": f"""<Relationships xmlns="{REL}">
              <Relationship Id="rId1" Type="slide" Target="slides/slide1.xml"/>
              <Relationship Id="rId2" Type="slide" Target="slides/slide2.xml"/>
            </Relationships>""",
            "ppt/slides/slide1.xml": slide("Second slide"),
            "ppt/slides/slide2.xml": slide("First slide"),
            "ppt/slides/_rels/slide2.xml.rels": f"""<Relationships xmlns="{REL}">
              <Relationship Id="notes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide2.xml"/>
            </Relationships>""",
            "ppt/notesSlides/notesSlide2.xml": notes,
        },
    )

    [source] = load([path])

    assert source.kind == "pptx"
    assert source.text == (
        "[slide 1]\nFirst slide\n[notes]\nConfirm the target"
        "\n\n[slide 2]\nSecond slide"
    )
    assert "99" not in source.text
    assert as_prompt(load([path])) == as_prompt(load([path]))


def test_text_file_in_cp1252_loads_without_losing_accents(tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_bytes(b"Caf\xe9 notes\n")

    [source] = load([notes])

    assert source.kind == "text"
    assert source.text == "Café notes\n"


def test_text_file_with_utf8_bom_drops_the_bom(tmp_path):
    notes = tmp_path / "notes.md"
    notes.write_bytes("\ufeffCafé notes\n".encode("utf-8"))

    [source] = load([notes])

    assert source.text == "Café notes\n"


def test_text_file_with_bytes_undefined_in_cp1252_still_loads(tmp_path):
    notes = tmp_path / "export.csv"
    notes.write_bytes(b"id;name\n1;Caf\xe9 \x81\n")

    [source] = load([notes])

    assert source.text.startswith("id;name\n1;Caf")
    assert "\x81" in source.text  # latin-1 keeps the byte instead of raising

def test_pdf_without_extractable_text_produces_warning(tmp_path):
    path = tmp_path / "scanned.pdf"

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(path)

    [source] = load([path])

    assert source.kind == "pdf"
    assert source.text == ""
    assert source.warning == "no text found (scanned?)"


def test_password_protected_pdf_produces_warning(tmp_path):
    path = tmp_path / "protected.pdf"

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("test-password")
    writer.write(path)

    [source] = load([path])

    assert source.kind == "pdf"
    assert source.text == ""
    assert source.warning == "password-protected PDF"


def test_corrupted_pdf_does_not_stop_other_documents(tmp_path):
    broken = tmp_path / "broken.pdf"
    valid = tmp_path / "notes.txt"

    broken.write_bytes(b"This is not a valid PDF")
    valid.write_text("Valid document content", encoding="utf-8")

    sources = load([broken, valid])

    assert len(sources) == 2
    assert sources[0].warning
    assert sources[1].text == "Valid document content"
