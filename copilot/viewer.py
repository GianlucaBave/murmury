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