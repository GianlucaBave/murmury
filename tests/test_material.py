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


def _docx(path: Path, body: str) -> None:
    _archive(
        path,
        {
            "word/document.xml": (
                f'<w:document xmlns:w="{W}">'
                f"<w:body>{body}</w:body></w:document>"
            ),
        },
    )


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


# Test 1: Tab preservation

def test_docx_preserves_tabs_between_words(tmp_path):
    path = tmp_path / "brief.docx"

    _docx(
        path,
        '<w:p><w:r><w:t>Name</w:t><w:tab/><w:t>Value</w:t></w:r></w:p>',
    )

    [source] = load([path])

    assert source.text == "Name\tValue"
    assert source.warning is None


# Test 2: Line breaks

def test_docx_line_breaks_inside_paragraph(tmp_path):
    path = tmp_path / "brief.docx"

    _docx(
        path,
        '<w:p><w:r><w:t>First</w:t><w:br/>'
        '<w:t>Second</w:t><w:cr/><w:t>Third</w:t></w:r></w:p>',
    )

    [source] = load([path])

    assert source.text == "First\nSecond\nThird"
    assert source.warning is None


# Test 3: Empty paragraphs and whitespace trimming

def test_docx_drops_empty_paragraphs_and_trims_spaces(tmp_path):
    path = tmp_path / "brief.docx"

    _docx(
        path,
        '<w:p><w:r><w:t>A</w:t></w:r></w:p>'
        '<w:p/>'
        '<w:p><w:r><w:t xml:space="preserve">   </w:t></w:r></w:p>'
        '<w:p><w:r><w:t xml:space="preserve">  B  </w:t></w:r></w:p>',
    )

    [source] = load([path])

    assert source.text == "A\n\nB"
    assert source.warning is None


# Test 4: Multiple paragraphs inside a table cell

def test_docx_multiple_paragraphs_inside_table_cell(tmp_path):
    path = tmp_path / "brief.docx"

    _docx(
        path,
        '<w:tbl><w:tr>'
        '<w:tc>'
        '<w:p><w:r><w:t>First</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Second</w:t></w:r></w:p>'
        '</w:tc>'
        '<w:tc><w:p><w:r><w:t>Other</w:t></w:r></w:p></w:tc>'
        '</w:tr></w:tbl>',
    )

    [source] = load([path])

    assert source.text == "First Second | Other"
    assert source.warning is None


# Test 5A: Empty table rows must be ignored

def test_docx_drops_table_rows_with_no_text(tmp_path):
    path = tmp_path / "brief.docx"

    _docx(
        path,
        '<w:p><w:r><w:t>Header</w:t></w:r></w:p>'
        '<w:tbl><w:tr>'
        '<w:tc><w:p><w:r><w:t>Q1</w:t></w:r></w:p></w:tc>'
        '<w:tc><w:p><w:r><w:t>10</w:t></w:r></w:p></w:tc>'
        '</w:tr><w:tr>'
        '<w:tc><w:p/></w:tc>'
        '<w:tc><w:p><w:r><w:t xml:space="preserve">  </w:t></w:r></w:p></w:tc>'
        '</w:tr><w:tr>'
        '<w:tc><w:p><w:r><w:t>Q3</w:t></w:r></w:p></w:tc>'
        '<w:tc><w:p><w:r><w:t>30</w:t></w:r></w:p></w:tc>'
        '</w:tr></w:tbl>'
        '<w:p><w:r><w:t>Footer</w:t></w:r></w:p>',
    )

    [source] = load([path])

    assert source.text == "Header\n\nQ1 | 10\nQ3 | 30\n\nFooter"
    assert source.warning is None


# Test 5B: An empty table must not add a block

def test_docx_empty_table_adds_no_block(tmp_path):
    path = tmp_path / "brief.docx"

    _docx(
        path,
        '<w:p><w:r><w:t>A</w:t></w:r></w:p>'
        '<w:tbl><w:tr>'
        '<w:tc><w:p/></w:tc>'
        '</w:tr></w:tbl>'
        '<w:p><w:r><w:t>B</w:t></w:r></w:p>',
    )

    [source] = load([path])

    assert source.text == "A\n\nB"
    assert source.warning is None


# Test 6: Empty Word document warning

def test_docx_empty_body_produces_no_text_warning(tmp_path):
    path = tmp_path / "empty.docx"

    _archive(
        path,
        {
            "word/document.xml": (
                f'<w:document xmlns:w="{W}"><w:body/>'
                '</w:document>'
            ),
        },
    )

    [source] = load([path])

    assert source.kind == "docx"
    assert source.text == ""
    assert source.warning == "no text found"


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


def test_pptx_slide_with_no_text_still_gives_slide_marker(tmp_path):
    path = tmp_path / "empty_slide.pptx"
    empty_slide = (
        f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:txBody>'
        f"<a:p/>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )
    _archive(
        path,
        {
            "ppt/presentation.xml": f"""<p:presentation xmlns:p="{P}" xmlns:r="{R}">
              <p:sldIdLst><p:sldId id="1" r:id="rId1"/></p:sldIdLst>
            </p:presentation>""",
            "ppt/_rels/presentation.xml.rels": f"""<Relationships xmlns="{REL}">
              <Relationship Id="rId1" Type="slide" Target="slides/slide1.xml"/>
            </Relationships>""",
            "ppt/slides/slide1.xml": empty_slide,
        },
    )

    [source] = load([path])

    assert source.kind == "pptx"
    assert source.text == "[slide 1]"
    assert source.warning is None


def test_pptx_missing_relationship_skips_slide_preserving_subsequent_numbers(tmp_path):
    path = tmp_path / "missing_rel.pptx"
    slide = lambda text: (
        f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:txBody>'
        f"<a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )
    _archive(
        path,
        {
            "ppt/presentation.xml": f"""<p:presentation xmlns:p="{P}" xmlns:r="{R}">
              <p:sldIdLst>
                <p:sldId id="1" r:id="rId1"/>
                <p:sldId id="2" r:id="rIdMissing"/>
                <p:sldId id="3" r:id="rId3"/>
              </p:sldIdLst>
            </p:presentation>""",
            "ppt/_rels/presentation.xml.rels": f"""<Relationships xmlns="{REL}">
              <Relationship Id="rId1" Type="slide" Target="slides/slide1.xml"/>
              <Relationship Id="rId3" Type="slide" Target="slides/slide3.xml"/>
            </Relationships>""",
            "ppt/slides/slide1.xml": slide("Slide One"),
            "ppt/slides/slide3.xml": slide("Slide Three"),
        },
    )

    [source] = load([path])

    assert source.kind == "pptx"
    assert source.text == "[slide 1]\nSlide One\n\n[slide 3]\nSlide Three"


def test_pptx_relationship_target_starting_with_slash_is_found(tmp_path):
    path = tmp_path / "absolute_target.pptx"
    slide = lambda text: (
        f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:txBody>'
        f"<a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )
    _archive(
        path,
        {
            "ppt/presentation.xml": f"""<p:presentation xmlns:p="{P}" xmlns:r="{R}">
              <p:sldIdLst><p:sldId id="1" r:id="rId1"/></p:sldIdLst>
            </p:presentation>""",
            "ppt/_rels/presentation.xml.rels": f"""<Relationships xmlns="{REL}">
              <Relationship Id="rId1" Type="slide" Target="/ppt/slides/slide1.xml"/>
            </Relationships>""",
            "ppt/slides/slide1.xml": slide("Absolute path target"),
        },
    )

    [source] = load([path])

    assert source.kind == "pptx"
    assert source.text == "[slide 1]\nAbsolute path target"


def test_pptx_notes_with_only_date_or_footer_add_no_notes_block(tmp_path):
    path = tmp_path / "date_footer_notes.pptx"
    slide = lambda text: (
        f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:txBody>'
        f"<a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )
    notes = f"""<p:notes xmlns:p="{P}" xmlns:a="{A}"><p:cSld>
      <p:sp><p:nvSpPr><p:nvPr><p:ph type="dt"/></p:nvPr></p:nvSpPr><p:txBody>
        <a:p><a:r><a:t>2026-11-20</a:t></a:r></a:p>
      </p:txBody></p:sp>
      <p:sp><p:nvSpPr><p:nvPr><p:ph type="ftr"/></p:nvPr></p:nvSpPr><p:txBody>
        <a:p><a:r><a:t>Confidential</a:t></a:r></a:p>
      </p:txBody></p:sp>
    </p:cSld></p:notes>"""
    _archive(
        path,
        {
            "ppt/presentation.xml": f"""<p:presentation xmlns:p="{P}" xmlns:r="{R}">
              <p:sldIdLst><p:sldId id="1" r:id="rId1"/></p:sldIdLst>
            </p:presentation>""",
            "ppt/_rels/presentation.xml.rels": f"""<Relationships xmlns="{REL}">
              <Relationship Id="rId1" Type="slide" Target="slides/slide1.xml"/>
            </Relationships>""",
            "ppt/slides/slide1.xml": slide("Slide content"),
            "ppt/slides/_rels/slide1.xml.rels": f"""<Relationships xmlns="{REL}">
              <Relationship Id="notes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide1.xml"/>
            </Relationships>""",
            "ppt/notesSlides/notesSlide1.xml": notes,
        },
    )

    [source] = load([path])

    assert source.kind == "pptx"
    assert source.text == "[slide 1]\nSlide content"
    assert "[notes]" not in source.text
    assert "Confidential" not in source.text
    assert "2026-11-20" not in source.text


def test_pptx_slide_without_relationship_file_has_no_notes(tmp_path):
    path = tmp_path / "no_slide_rels.pptx"
    slide = lambda text: (
        f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:txBody>'
        f"<a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )
    _archive(
        path,
        {
            "ppt/presentation.xml": f"""<p:presentation xmlns:p="{P}" xmlns:r="{R}">
              <p:sldIdLst><p:sldId id="1" r:id="rId1"/></p:sldIdLst>
            </p:presentation>""",
            "ppt/_rels/presentation.xml.rels": f"""<Relationships xmlns="{REL}">
              <Relationship Id="rId1" Type="slide" Target="slides/slide1.xml"/>
            </Relationships>""",
            "ppt/slides/slide1.xml": slide("Slide without notes rels"),
        },
    )

    [source] = load([path])

    assert source.kind == "pptx"
    assert source.text == "[slide 1]\nSlide without notes rels"
    assert "[notes]" not in source.text


def test_pptx_without_presentation_relationships_produces_warning(tmp_path):
    path = tmp_path / "no_rels.pptx"
    slide = lambda text: (
        f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:txBody>'
        f"<a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )
    _archive(
        path,
        {
            "ppt/presentation.xml": f"""<p:presentation xmlns:p="{P}" xmlns:r="{R}">
              <p:sldIdLst><p:sldId id="1" r:id="rId1"/></p:sldIdLst>
            </p:presentation>""",
            "ppt/slides/slide1.xml": slide("Orphan slide"),
        },
    )

    [source] = load([path])

    assert source.kind == "pptx"
    assert source.text == ""
    assert source.warning == "no text found"


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
    assert sources[0].warning == "could not read PDF"
    assert sources[1].text == "Valid document content"
    assert sources[1].warning is None


def test_broken_docx_does_not_stop_other_documents(tmp_path):
    broken = tmp_path / "broken.docx"
    valid = tmp_path / "notes.txt"

    broken.write_bytes(b"This is not a valid DOCX file")
    valid.write_text("Valid document content", encoding="utf-8")

    sources = load([broken, valid])

    assert len(sources) == 2
    assert sources[0].kind == "docx"
    assert sources[0].text == ""
    assert sources[0].warning == "could not read DOCX"
    assert sources[1].kind == "text"
    assert sources[1].text == "Valid document content"
    assert sources[1].warning is None


def test_empty_text_file_produces_warning(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")

    [source] = load([path])

    assert source.kind == "text"
    assert source.text == ""
    assert source.warning == "no text found"
