"""The source viewer: shows the cited passage of a document inside Murmury, hidden from screen sharing.

These functions choose what to show from a source tag. They need no window, so they are tested without a screen.
"""

from __future__ import annotations

import re


NAME_ENDS = " ,:!#[" # what may follow a file name in a tag: "plan.pdf, page 12", "notes.md#Pricing"


def after_name(tag: str, name: str) -> str | None:
    """What a tag says after the file's name ("plan.pdf, page 12" -> "page 12"), or None if the tag does
    not start with that name. The name must end at a separator, so "plan.pdf.evil" is not "plan.pdf"."""
    if not tag.casefold().startswith(name.casefold()):
        return None
    rest = tag[len(name):]
    if rest and rest[0] not in NAME_ENDS:
        return None
    return rest.lstrip(NAME_ENDS).strip()


PAGE = re.compile(r"\b(?:pages?|pp?\.|pg\.?)\s*(\d+)", re.IGNORECASE)


def page_from_tag(text: str) -> int | None:
    """The page number a tag cites ("page 12", "p. 12", "pp. 12-13" -> 12), or None. Only a number after a
    page word counts: "Table 8" and "§4.2" are not pages."""
    match = PAGE.search(text)
    return int(match.group(1)) if match else None


def pdf_index(tag: str, name: str, page_count: int) -> tuple[int, str | None]:
    """The page to open, counted from 0 as QtPdf counts, and a message when it is not the cited page.
    Pages are counted as material.py counts them: the first page of the file is page 1."""
    rest = after_name(tag, name)
    number = page_from_tag(tag if rest is None else rest)
    if number is None:
        return 0, (f"No page number in [{tag}]: showing page 1" if tag else None)
    if not 1 <= number <= page_count:
        return 0, f"{name} has no page {number} (it has {page_count}): showing page 1"
    return number - 1, None


def words(text: str) -> list[str]:
    """The words of a text in lower case, for comparing a tag with a heading: "§4.2 Go-to-market" ->
    ["4.2", "go", "to", "market"]. A number like 4.2 stays one word."""
    return re.findall(r"\w+(?:\.\w+)*", text.casefold())


HEADING = re.compile(r"(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = ("```", "~~~")


def headings(text: str) -> list[tuple[int, int, str]]:
    """The Markdown headings in a text: where each starts (a character offset), its level (1 for #, 2 for ##...)
    and its title. Lines inside ``` code blocks are not headings, even when they start with #."""
    found, offset, in_code = [], 0, False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(FENCE):
            in_code = not in_code
        elif not in_code:
            match = HEADING.match(line)
            if match:
                found.append((offset, len(match.group(1)), match.group(2)))
        offset += len(line)
    return found


def heading_index(found: list[tuple[int, int, str]], wanted: list[str]) -> int | None:
    """The position in `found` of the heading a tag means: first a title equal to the tag, then a title that
    starts with it ("4.2" finds "4.2 Go-to-market"), or None."""
    for index, (_, _, title) in enumerate(found):
        if words(title) == wanted:
            return index
    for index, (_, _, title) in enumerate(found):
        if words(title)[:len(wanted)] == wanted:
            return index
    return None


def find_section(tag: str, name: str, text: str) -> tuple[int, int, str | None]:
    """The part of a Markdown or text file a heading tag cites: its start and end (character offsets) and a
    message when no heading matches. A section runs from its heading to the next heading of the same or a
    higher level, so it includes its subsections."""
    rest = after_name(tag, name)
    wanted = words(tag if rest is None else rest)
    found = headings(text)
    index = heading_index(found, wanted) if wanted else None
    if index is None:
        return 0, len(text), (f"No heading [{tag}] in {name}: showing the start" if tag else None)
    start, level, _ = found[index]
    end = len(text)
    for later_start, later_level, _ in found[index + 1:]:
        if later_level <= level:
            end = later_start
            break
    return start, end, None