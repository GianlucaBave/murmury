"""The material the copilot answers from: the files chosen before the call, turned into text.

PDF pages keep their page number, so an answer can point to it. Spreadsheets keep their cached
values (the numbers Excel last computed), sheet by sheet; hidden sheets are skipped. Word blocks
and PowerPoint slides retain their document order, and presentation notes stay with their slide.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


@dataclass(frozen=True)
class Source:
    name: str
    kind: str  # "pdf", "xlsx", "docx", "pptx", "text"
    text: str


def _pdf(path: Path) -> str:
    from pypdf import PdfReader

    pages = []
    for number, page in enumerate(PdfReader(path).pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"[page {number}]\n{text}")
    return "\n\n".join(pages)


def _cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".") if abs(value) < 10 else f"{value:,.0f}"
    return str(value)


def _xlsx(path: Path) -> str:
    from openpyxl import load_workbook

    book = load_workbook(path, data_only=True, read_only=False)
    sheets = []
    for sheet in book.worksheets:
        if sheet.sheet_state != "visible":
            continue
        rows = []
        for row in sheet.iter_rows():
            cells = [f"{c.coordinate}={_cell(c.value)}" for c in row if c.value not in (None, "")]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            sheets.append(f"[sheet {sheet.title}]\n" + "\n".join(rows))
    return "\n\n".join(sheets)


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_IGNORED_NOTE_PLACEHOLDERS = {"sldNum", "dt", "hdr", "ftr", "sldImg"}


def _paragraph_text(paragraph: ET.Element, *, word: bool = False) -> str:
    text_tag = _W + "t" if word else _A + "t"
    tab_tag = _W + "tab"
    break_tags = {_W + "br", _W + "cr"}
    parts = []
    for element in paragraph.iter():
        if element.tag == text_tag:
            parts.append(element.text or "")
        elif word and element.tag == tab_tag:
            parts.append("\t")
        elif word and element.tag in break_tags:
            parts.append("\n")
    return "".join(parts).strip()


def _docx(path: Path) -> str:
    with ZipFile(path) as archive:
        body = ET.fromstring(archive.read("word/document.xml")).find(_W + "body")
        if body is None:
            return ""

        blocks = []
        for block in body:
            if block.tag == _W + "p":
                text = _paragraph_text(block, word=True)
                if text:
                    blocks.append(text)
            elif block.tag == _W + "tbl":
                rows = []
                for row in block.findall(_W + "tr"):
                    cells = []
                    for cell in row.findall(_W + "tc"):
                        paragraphs = [
                            text
                            for paragraph in cell.findall(_W + "p")
                            if (text := _paragraph_text(paragraph, word=True))
                        ]
                        cells.append(" ".join(paragraphs))
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    blocks.append("\n".join(rows))
        return "\n\n".join(blocks)


def _relationship_targets(archive: ZipFile, relationships_path: str) -> dict[str, str]:
    try:
        root = ET.fromstring(archive.read(relationships_path))
    except KeyError:
        return {}
    return {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in root.findall(_REL + "Relationship")
    }


def _resolve_target(base: str, target: str) -> str:
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(posixpath.join(base, target))


def _presentation_notes(archive: ZipFile, slide_path: str) -> str:
    rels_path = posixpath.join(
        posixpath.dirname(slide_path),
        "_rels",
        posixpath.basename(slide_path) + ".rels",
    )
    try:
        relationships = ET.fromstring(archive.read(rels_path))
    except KeyError:
        return ""
    for relationship in relationships.findall(_REL + "Relationship"):
        if not relationship.attrib.get("Type", "").endswith("/notesSlide"):
            continue
        notes_path = _resolve_target(
            posixpath.dirname(slide_path), relationship.attrib["Target"]
        )
        notes = ET.fromstring(archive.read(notes_path))
        paragraphs = []
        for shape in notes.iter(_P + "sp"):
            placeholder = shape.find("./" + _P + "nvSpPr/" + _P + "nvPr/" + _P + "ph")
            if placeholder is not None and placeholder.attrib.get("type") in _IGNORED_NOTE_PLACEHOLDERS:
                continue
            text_body = shape.find(_P + "txBody")
            if text_body is None:
                continue
            paragraphs.extend(
                text
                for paragraph in text_body.findall(_A + "p")
                if (text := _paragraph_text(paragraph))
            )
        return "\n".join(paragraphs)
    return ""


def _pptx(path: Path) -> str:
    with ZipFile(path) as archive:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        relationships = _relationship_targets(archive, "ppt/_rels/presentation.xml.rels")
        slides = presentation.findall("./" + _P + "sldIdLst/" + _P + "sldId")
        blocks = []
        for number, slide_id in enumerate(slides, start=1):
            target = relationships.get(slide_id.attrib.get(_R + "id", ""))
            if not target:
                continue
            slide_path = _resolve_target("ppt", target)
            slide = ET.fromstring(archive.read(slide_path))
            paragraphs = [
                text
                for paragraph in slide.iter(_A + "p")
                if (text := _paragraph_text(paragraph))
            ]
            block = f"[slide {number}]"
            if paragraphs:
                block += "\n" + "\n".join(paragraphs)
            notes = _presentation_notes(archive, slide_path)
            if notes:
                block += "\n[notes]\n" + notes
            blocks.append(block)
        return "\n\n".join(blocks)


def _text(path: Path) -> str:
    """UTF-8 first (a BOM is dropped), then cp1252 for older notes and exports, then latin-1, which
    maps every byte, so a stray file never stops the whole call."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="latin-1")


def load(paths: list[Path]) -> list[Source]:
    sources = []
    for path in paths:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            sources.append(Source(path.name, "pdf", _pdf(path)))
        elif suffix in (".xlsx", ".xlsm"):
            sources.append(Source(path.name, "xlsx", _xlsx(path)))
        elif suffix == ".docx":
            sources.append(Source(path.name, "docx", _docx(path)))
        elif suffix == ".pptx":
            sources.append(Source(path.name, "pptx", _pptx(path)))
        else:
            sources.append(Source(path.name, "text", _text(path)))
    return sources


def as_prompt(sources: list[Source]) -> str:
    """One stable block of text: same files in, same bytes out, so the prompt cache holds."""
    return "\n\n".join(f'<source name="{s.name}" kind="{s.kind}">\n{s.text}\n</source>' for s in sources)
