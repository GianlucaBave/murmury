"""Does a source tag point to a place that exists in the document it names?

A tag is what the model writes at the end of a line, in square brackets: "page 12", "plan.pdf, slide 3",
"Sales!B4", a heading. This checks it against the text material.py loaded, using the anchors the loaders
write: [page N], [sheet NAME] with cells like B4=..., [slide N], and the Markdown headings of a text. Pages
and headings are compared the way the viewer compares them (copilot/viewer.py), so the check and the viewer
agree on what "the same place" means. A tag that is only the file's name points to the document and passes.
"""

from __future__ import annotations

import html
import re

from .material import Source
from .viewer import after_name, heading_index, headings, page_from_tag, words

FILE_WORD = re.compile(r"\.(pdf|xlsx|xlsm|docx|pptx|md|markdown|txt)\b", re.IGNORECASE)
CELL = re.compile(r"(?:(?P<sheet>[^!]+)!)?\$?(?P<column>[A-Za-z]{1,3})\$?(?P<row>\d{1,7})")


def _numbers(text: str, word: str) -> set[int]:
    """The numbers of the [page N] or [slide N] markers in a loaded text."""
    return {int(n) for n in re.findall(rf"^\[{word} (\d+)\]", text, flags=re.MULTILINE)}


def _sheets(text: str) -> dict[str, str]:
    """Each sheet's name and its lines, from the [sheet NAME] markers."""
    parts = re.split(r"^\[sheet (.+?)\][ \t]*$", text, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


def _sheet_name(value: str) -> str:
    value = value.strip().casefold()
    return value[6:].strip() if value.startswith("sheet ") else value


def _in_spreadsheet(rest: str, text: str) -> bool:
    sheets = _sheets(text)
    cell = CELL.fullmatch(rest.strip())
    if cell:
        coordinate = f"{cell['column'].upper()}{cell['row']}"
        for name, block in sheets.items():
            if cell["sheet"] is not None and _sheet_name(name) != _sheet_name(cell["sheet"]):
                continue
            if re.search(rf"(?:^|\| ){coordinate}=", block, flags=re.MULTILINE):
                return True
        return False
    named = re.fullmatch(r"sheets?\s+(.+)", rest.strip(), flags=re.IGNORECASE)
    return bool(named) and any(_sheet_name(name) == _sheet_name(named[1]) for name in sheets)


def _place_exists(rest: str, source: Source) -> bool:
    if source.kind == "pdf":
        page = page_from_tag(rest)
        if page is not None:
            return page in _numbers(source.text, "page")
    elif source.kind == "pptx":
        slide = re.fullmatch(r"slides?\s*(\d+)", rest, flags=re.IGNORECASE)
        if slide:
            return int(slide[1]) in _numbers(source.text, "slide")
    elif source.kind == "xlsx":
        return _in_spreadsheet(rest, source.text)
    wanted = words(rest)
    return bool(wanted) and heading_index(headings(source.text), wanted) is not None


def tag_exists(tag: str, source: Source) -> bool:
    """True when the tag points to a place that exists in this source, or is only the source's file name.

    The name is tried as written and unescaped, because the prompt gives names escaped (material.as_prompt).
    A tag that names another file does not point into this one."""
    for variant in dict.fromkeys((tag, html.unescape(tag))):
        rest = after_name(variant, source.name)
        if rest is None:
            if FILE_WORD.search(variant):
                continue
            rest = variant
        elif not rest.strip():
            return True
        if _place_exists(rest.strip(), source):
            return True
    return False
