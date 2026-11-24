"""The source viewer: shows the cited passage of a document inside Murmury, hidden from screen sharing.

The functions at the top choose what to show from a source tag; they need no window, so they are tested without a
screen. SourceViewer below is the window. app.py hides it from screen sharing, as it does the floating window.
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from . import theme

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


COMMON = frozenset("the and our for are was were with that this from have has its but not you your they their will can".split())
MIN_SHARE = 0.5  # share of a fact's key words a line must hold to be highlighted: a starting value, tune it on real calls

def key_words(text: str) -> list[str]:
    """The words that tell one line from another: numbers, and words of three letters or more that are not common
    little words ("we", "the", "and" say nothing about where a fact comes from)."""
    return [w for w in words(text) if any(c.isdigit() for c in w) or (len(w) >= 3 and w not in COMMON)]


def best_block(fact: str, text: str, start: int, end: int) -> tuple[int, int] | None:
    """The line of text[start:end] a fact line most likely comes from, as (start, end) offsets, or None when no
    line holds at least MIN_SHARE of the fact's key words. A wrong highlight is worse than none."""
    wanted = set(key_words(fact))
    if not wanted:
        return None
    best, best_share = None, 0.0
    offset = start
    for line in text[start:end].splitlines(keepends=True):
        share = len(wanted & set(key_words(line))) / len(wanted)
        if share > best_share:
            best, best_share = (offset, offset + len(line.rstrip("\r\n"))), share
        offset += len(line)
    return best if best_share >= MIN_SHARE else None


STYLE = """
#panel { background: $glass; border: 1px solid $panel_border; border-radius: 12px; }
QLabel { color: $text; }
#title { color: $secondary; font-size: 11px; }
#message { color: $tag_fg; background: $tag_bg; border-radius: 6px; padding: 4px 8px; font-size: 12px; }
QPushButton { background: transparent; border: none; color: $secondary; font-size: 13px; padding: 0 4px; }
QPushButton:hover { color: $link; }
"""

class SourceViewer(QWidget):
    """A small window that shows the cited passage. It is made once and reused: Close only hides it, which keeps
    its native window, and with it the hiding from screen sharing that app.py sets up."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Murmury source")
        self.resize(520, 640)
        self.drag = None
        self.path: Path | None = None
        self.tag = ""

        panel = QFrame(self, objectName="panel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(panel)
        box = QVBoxLayout(panel)
        box.setContentsMargins(14, 10, 14, 10)
        box.setSpacing(8)

        top = QHBoxLayout()
        self.title = QLabel("", objectName="title")
        top.addWidget(self.title, 1)
        open_in_app = QPushButton("Open in app")
        open_in_app.setToolTip("Opens the whole file in its own app, which screen sharing can see")
        open_in_app.clicked.connect(self.open_in_app)
        close = QPushButton("Close")
        close.clicked.connect(self.hide)
        for button in (open_in_app, close):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            top.addWidget(button)
        box.addLayout(top)

        self.message = QLabel("", objectName="message", wordWrap=True)
        self.message.hide()
        box.addWidget(self.message)

        self.document = QPdfDocument(self)
        self.document.statusChanged.connect(self.pdf_status)
        self.pdf = QPdfView(panel)
        self.pdf.setDocument(self.document)
        self.pdf.setPageMode(QPdfView.PageMode.SinglePage)
        self.pdf.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        box.addWidget(self.pdf, 1)

        QShortcut(QKeySequence("Escape"), self, self.hide)
        self.apply_theme()
        theme.watch(self.apply_theme)


    def apply_theme(self) -> None:
        self.setStyleSheet(theme.fill(STYLE))

    def say(self, message: str | None) -> None:
        """Show a short note above the document (why it is not at the cited place), or hide it when there is none."""
        self.message.setText(message or "")
        self.message.setVisible(bool(message))

    def show_pdf(self, path: Path, tag: str) -> None:
        """Open a PDF at the page the tag cites. The page is chosen in pdf_status, once the document is ready:
        until then it has no pages."""
        self.path, self.tag = path, tag
        self.title.setText(path.name)
        self.say(None)
        self.document.load(str(path))
        self.show()
        self.raise_()
        self.activateWindow()

    def pdf_status(self, status: QPdfDocument.Status) -> None:
        if status == QPdfDocument.Status.Ready:
            index, message = pdf_index(self.tag, self.path.name, self.document.pageCount())
            self.pdf.pageNavigator().jump(index, QPointF(), 0)
            self.say(message)
        elif status == QPdfDocument.Status.Error:
            self.say(f"Could not open {self.path.name} here: try Open in app")

    def open_in_app(self) -> None:
        """The second choice: the whole file in its own app, which screen sharing can see."""
        if self.path and not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path))):
            self.say(f"Could not open {self.path.name}")

    # drag anywhere on the window, as the floating window does
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag is not None:
            self.move(event.globalPosition().toPoint() - self.drag)

    def mouseReleaseEvent(self, event):
        self.drag = None