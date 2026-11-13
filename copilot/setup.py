"""The screen before the call: choose the documents, say what the call is, start.

Documents and names to transcribe start empty every time. Only the kind of call, the AI service and model,
and the prepare choice are remembered (in the macOS preferences), plus the last folder opened.
"""

from __future__ import annotations

from html import escape as html_escape

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from uuid import uuid4
from pathlib import Path

from PySide6.QtCore import QByteArray, QPoint, QRect, QRectF, QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame,
                               QHBoxLayout, QLabel, QLayout, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea,
                               QSlider, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from . import providers, theme
from .answer import PRESETS, Style
from .chrome import AppearanceButton, TrafficLights

SITUATIONS = [
    "a seed pitch to an investor",
    "a follow-up call with an investor who has read the documents",
    "a sales call with a prospective customer",
    "a negotiation with a partner",
]
REPO_URL = "https://github.com/GianlucaBave/murmury"
TYPES = "Documents (*.pdf *.xlsx *.xlsm *.docx *.pptx *.txt *.md)"
SUFFIXES = {".pdf", ".xlsx", ".xlsm", ".docx", ".pptx", ".txt", ".md"}

# Apple's type scale (13 pt body, 11-12 pt secondary), native controls, one accent (green); colours from theme.py.
STYLE = """
#panel { background: $panel; border: 1px solid $panel_border; border-radius: 12px; }
QLabel { color: $text; font-size: 13px; background: transparent; }
QLabel#title { font-size: 20px; font-weight: 700; color: $text; }
QLabel#bar_title { font-size: 13px; font-weight: 700; color: $text; }
QLabel#tour_body { color: $text; font-size: 13px; }
QFrame#callrow { background: $group; border: 1px solid $group_border; border-radius: 10px; }
QFrame#callrow:hover { border-color: $accent; }
QLabel#call_title { color: $text; font-size: 14px; font-weight: 600; }
QLabel#chevron { color: $tertiary; font-size: 18px; }
QPushButton#plus { background: $accent; color: white; border: none; border-radius: 32px; font-size: 34px;
    min-width: 64px; max-width: 64px; min-height: 64px; max-height: 64px; padding: 0 0 4px 0; }
QPushButton#plus:hover { background: $accent_hover; }
QPushButton#save { background: $accent; color: white; border: none; border-radius: 6px; padding: 4px 14px;
    font-size: 13px; font-weight: 600; }
QPushButton#save:hover { background: $accent_hover; }
QPushButton#save:disabled { background: $disabled_bg; color: $disabled_fg; }
QPushButton#back { background: transparent; border: none; color: $link; font-size: 28px; padding: 0 6px 3px 0; }
QPushButton#back:hover { color: $link_hover; }
QLineEdit#call_name { font-size: 20px; font-weight: 700; background: transparent; border: 1px solid transparent;
    border-radius: 6px; padding: 2px 4px; }
QLineEdit#call_name:hover { border-color: $input_border; }
QLineEdit#call_name:focus { border-color: $accent; background: $input; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QPushButton#help { background: transparent; border: 1px solid $button_border; border-radius: 10px; color: $secondary;
    font-size: 12px; font-weight: 600; min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; padding: 0; }
QPushButton#help:hover { color: $text; border-color: $secondary; }
QLabel#subtitle { color: $secondary; font-size: 12px; }
QLabel#section { color: $text; font-size: 13px; font-weight: 600; }
QLabel#muted { color: $secondary; font-size: 12px; }
QLabel#file { color: $text; font-size: 13px; }
QComboBox, QSpinBox, QLineEdit { color: $text; }
QLineEdit { background: $input; border: 1px solid $input_border; border-radius: 6px; padding: 3px 8px; }
QLineEdit:focus { border: 1px solid $accent; }
QComboBox:disabled, QSpinBox:disabled, QLineEdit:disabled { color: $faint; }
QFrame#group { background: $group; border: 1px solid $group_border; border-radius: 10px; }
QFrame#rule { background: $rule; max-height: 1px; min-height: 1px; border: none; }
QFrame#drop { background: $drop; border: 1px dashed $drop_border; border-radius: 10px; }
QFrame#drop:hover { border-color: $accent; background: $drop_hover; }
QPushButton#link { background: transparent; border: none; color: $link; padding: 1px 3px; font-size: 13px; }
QPushButton#link:hover { color: $link_hover; }
QPushButton#close { background: transparent; border: none; color: $tertiary; font-size: 14px; padding: 0 4px; }
QPushButton#close:hover { color: $text; }
QFrame#star { background: $group; border: 1px solid $accent; border-radius: 10px; }
QPushButton#remove { background: transparent; border: none; color: $faint; font-size: 13px; padding: 0 4px; }
QPushButton#remove:hover { color: $danger; }
QPushButton#cancel { background: $button; color: $text; border: 1px solid $button_border; border-radius: 6px;
    padding: 4px 14px; font-size: 13px; }
QPushButton#cancel:hover { background: $button_hover; }
QPushButton#start { background: $accent; color: white; border: none; border-radius: 6px; padding: 5px 16px;
    font-size: 13px; font-weight: 600; }
QPushButton#start:hover { background: $accent_hover; }
QPushButton#start:disabled { background: $disabled_bg; color: $disabled_fg; }
QPushButton#seg { background: transparent; border: 1px solid transparent; color: $text; border-radius: 5px;
    padding: 2px 12px; font-size: 12px; }
QPushButton#seg:checked { background: $seg_on; border: 1px solid $seg_on_border; }
QFrame#segbar { background: $segbar; border-radius: 7px; }
QFrame#textbox { background: $input; border: 1px solid $input_border; border-radius: 8px; }
QFrame#textbox QPlainTextEdit { background: transparent; border: none; color: $text; font-size: 13px; }
QLabel#counter { color: $faint; font-size: 11px; }
QSlider::groove:horizontal { height: 4px; background: $segbar; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal { background: white; border: 1px solid $button_border; width: 16px; height: 16px;
    margin: -7px 0; border-radius: 8px; }
QFrame#preview { background: $card; border: 1px solid $card_border; border-radius: 10px; }
QLabel#preview_say { color: $text; font-size: 13px; font-weight: 600; }
QLabel#preview_line { color: $text; font-size: 12px; }
"""

UPLOAD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#86868b"
stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4"/><path d="M7.5 8.5 12 4l4.5 4.5"/>
<path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/></svg>"""
FILE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#1fa463"
stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10
a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>"""

TONE_LABELS = [("Confident", "confident"), ("Neutral", "neutral"), ("Cautious", "cautious")]
FORMAT_LABELS = [("Talking points", "talking"), ("Key facts", "facts"), ("Script", "script")]
LANGUAGES = [("Same as question", ""), ("English", "English"), ("Italian", "Italian"), ("German", "German"),
             ("French", "French"), ("Spanish", "Spanish")]


def app_icon(size: int) -> QPixmap:
    """Murmury's icon, from the packaged app's resources or drawn from the build script when run from source."""
    import sys
    for candidate in (Path(getattr(sys, "_MEIPASS", "")) / "copilot" / "assets" / "icon.png",
                      Path(__file__).parent / "assets" / "icon.png"):
        if candidate.exists():
            pixmap = QPixmap(str(candidate)).scaled(size * 2, size * 2, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation)
            pixmap.setDevicePixelRatio(2)
            return pixmap
    return QPixmap()


def icon(svg: str, size: int) -> QPixmap:
    pixmap = QPixmap(QSize(size, size) * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return pixmap


class Switch(QAbstractButton):
    """A macOS-style on/off switch."""

    def __init__(self, checked: bool = False):
        super().__init__(checkable=True, checked=checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(34, 20)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(1.0 if self.isEnabled() else 0.35)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.palette()["accent"] if self.isChecked() else theme.palette()["switch_off"]))
        p.drawRoundedRect(QRectF(0, 0, 34, 20), 10, 10)
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(16 if self.isChecked() else 2, 2, 16, 16))


class Segmented(QFrame):
    """A segmented control: one choice among a few, all visible."""
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]]):
        super().__init__(objectName="segbar")
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(2)
        self.group = QButtonGroup(self, exclusive=True)
        self.buttons: dict[str, QPushButton] = {}
        for label, value in options:
            b = QPushButton(label, objectName="seg", checkable=True, cursor=Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=value: self.changed.emit(v))
            self.group.addButton(b)
            self.buttons[value] = b
            row.addWidget(b)

    def value(self) -> str:
        return next((v for v, b in self.buttons.items() if b.isChecked()), "")

    def set_value(self, value: str) -> None:
        if value in self.buttons:
            self.buttons[value].setChecked(True)
        else:  # no option matches (a custom preset): show none selected
            self.group.setExclusive(False)
            for b in self.buttons.values():
                b.setChecked(False)
            self.group.setExclusive(True)


class CallRow(QFrame):
    """One saved call in the list: its name, what it holds, and a chevron. Click to open it."""
    clicked = Signal(str)

    def __init__(self, call: dict):
        super().__init__(objectName="callrow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.call_id = call["id"]
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(QLabel(call.get("name") or "Untitled call", objectName="call_title"))
        docs = len(call.get("docs", []))
        service = providers.provider(call.get("provider")).name.split(" ·")[0]
        detail = [f"{docs} document{'s' if docs != 1 else ''}", service] + ([call["model"]] if call.get("model") else [])
        if call.get("situation"):
            detail.append(" ".join(call["situation"].split()[:8]) + ("…" if len(call["situation"].split()) > 8 else ""))
        text.addWidget(QLabel(" · ".join(detail), objectName="muted"))
        row.addLayout(text, 1)
        row.addWidget(QLabel("›", objectName="chevron"))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.call_id)


class TextBox(QFrame):
    """A few lines of free text with a visible character limit."""
    changed = Signal()

    def __init__(self, placeholder: str, limit: int, lines: int = 3):
        super().__init__(objectName="textbox")
        box = QVBoxLayout(self)
        box.setContentsMargins(8, 6, 10, 4)
        box.setSpacing(0)
        self.edit = QPlainTextEdit(placeholderText=placeholder)
        self.edit.setFrameShape(QFrame.Shape.NoFrame)
        self.edit.setTabChangesFocus(True)
        self.edit.setFixedHeight(lines * 18 + 10)
        self.counter = QLabel("", objectName="counter", alignment=Qt.AlignmentFlag.AlignRight)
        box.addWidget(self.edit)
        box.addWidget(self.counter)
        self.limit = limit
        self.edit.textChanged.connect(self._changed)
        self._changed()

    def _changed(self) -> None:
        text = self.edit.toPlainText()
        if len(text) > self.limit:  # typed or pasted past the limit: cut, keep the cursor where it was
            at = min(self.edit.textCursor().position(), self.limit)
            self.edit.blockSignals(True)
            self.edit.setPlainText(text[:self.limit])
            self.edit.blockSignals(False)
            cursor = self.edit.textCursor()
            cursor.setPosition(at)
            self.edit.setTextCursor(cursor)
            text = text[:self.limit]
        self.counter.setText(f"{len(text)}/{self.limit}")
        self.changed.emit()

    def text(self) -> str:
        return self.edit.toPlainText()

    def setText(self, text: str) -> None:
        self.edit.setPlainText(text[:self.limit])


class Slider(QWidget):
    """A slider with its value written next to it ("12 words")."""
    valueChanged = Signal(int)

    def __init__(self, low: int, high: int, one: str, many: str):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.slider = QSlider(Qt.Orientation.Horizontal, minimum=low, maximum=high)
        self.slider.setFixedWidth(170)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label = QLabel("", objectName="muted")
        self.label.setFixedWidth(82)
        self.one, self.many = one, many
        row.addWidget(self.slider)
        row.addWidget(self.label)
        self.slider.valueChanged.connect(self._changed)
        self._changed(self.slider.value())

    def _changed(self, value: int) -> None:
        self.label.setText(f"{value} {self.one if value == 1 else self.many}")
        self.valueChanged.emit(value)

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, value: int) -> None:
        self.slider.setValue(value)


# the preview shows an example answer cut to the chosen shape
PREVIEW_SAY = "We designed for IT approval from day one, and the plan already prices in a weak pipeline"
PREVIEW_FACTS = [("IT: one outbound connector, ERP untouched", "§7.9.1"), ("Win rate: 24% assumed in the plan", "§9.7"),
                 ("Guardrail: under 80 customers by Year 2 slows the roadmap", "§9.5"),
                 ("Design partners: two running it in their own cloud", "§6.2"),
                 ("Sales cycle: four months in the plan", "Table 12"), ("CAC payback: 14 months", "KPI sheet, B9")]
PREVIEW_LINES = [("IT only needs one outbound connector, and the customer's ERP stays untouched", "§7.9.1"),
                 ("We plan on a 24% win rate and stay profitable if it slips", "§9.7"),
                 ("Below 80 customers by Year 2, we slow the roadmap instead of burning cash", "§9.5"),
                 ("Our first two design partners already run it in their own cloud", "§6.2"),
                 ("That is why our sales cycle in the plan is only four months", "Table 12"),
                 ("And each new customer pays back its acquisition cost within 14 months", "KPI sheet, B9")]


class Group(QFrame):
    """A rounded group of rows, label on the left and control on the right, thin rules between."""

    def __init__(self):
        super().__init__(objectName="group")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(12, 2, 12, 2)
        self.box.setSpacing(0)
        self.rows: list[QWidget] = []

    def add(self, label: str | QWidget, *controls: QWidget, stretch: bool = False) -> QWidget:
        if self.rows:
            self.box.addWidget(QFrame(objectName="rule"))
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 5, 0, 5)
        line.setSpacing(8)
        line.addWidget(QLabel(label) if isinstance(label, str) else label)
        if not stretch:
            line.addStretch(1)
        for i, c in enumerate(controls):
            line.addWidget(c, 1 if stretch and i == 0 else 0)
        self.box.addWidget(row)
        self.rows.append(row)
        return row


class DropZone(QFrame):
    """The empty state of the document list: an upload icon and a hint; a click opens the file picker."""
    clicked = Signal()

    def __init__(self):
        super().__init__(objectName="drop")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(76)
        box = QVBoxLayout(self)
        box.setSpacing(4)
        picture = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        picture.setPixmap(icon(UPLOAD_SVG, 24))
        box.addWidget(picture)
        box.addWidget(QLabel("Drop PDF, Excel or text files, or click to choose", objectName="muted",
                             alignment=Qt.AlignmentFlag.AlignCenter))

    def mouseReleaseEvent(self, event):
        self.clicked.emit()


@dataclass
class Config:
    docs: list[str] = field(default_factory=list)
    situation: str = SITUATIONS[0]
    vocabulary: str = ""
    prepare: int = 0
    model: str = "claude-sonnet-5-5"
    style: Style = field(default_factory=Style)
    provider: str = providers.DEFAULT
    address: str = ""  # Ollama / LM Studio on another computer; empty: this Mac


def default_provider(settings: QSettings | None = None) -> str:
    """The AI service chosen last time, else Anthropic."""
    settings = settings or settings_store()
    return providers.provider(settings.value("provider")).id


def suggest_vocabulary(paths: list[Path], limit: int = 20) -> str:
    """Names that recur in the documents, which the speech model would otherwise mishear: words that are
    almost always capitalised (proper nouns), or written in capitals (acronyms)."""
    from . import material

    capital: Counter[str] = Counter()
    lower: Counter[str] = Counter()
    for source in material.load(paths):
        for word in re.findall(r"\b[A-Za-z][A-Za-z&-]{1,}\b", source.text):
            (capital if word[0].isupper() else lower)[word.lower() if not word[0].isupper() else word] += 1
    dictionary = _dictionary()

    def ordinary(word: str) -> bool:  # a dictionary word, or an inflection of one: not a name
        forms = {word, word.lower()} | {word.lower()[: -len(end)] for end in ("s", "es", "ed", "d", "ing")
                                          if word.lower().endswith(end)}
        return bool(forms & dictionary)

    months = {"Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec"}
    names = [w for w, n in capital.most_common(400)
             if n >= 3 and len(w) > 2 and lower[w.lower()] * 4 < n and not ordinary(w) and w not in months]
    return ", ".join(names[:limit])


def _dictionary() -> set[str]:
    words = Path("/usr/share/dict/words")  # present on macOS; without it, no filtering
    return set(words.read_text(errors="ignore").split()) if words.exists() else set()


def settings_store() -> QSettings:
    """Murmury's preferences; the first time, the ones saved under the app's earlier name are copied over."""
    import os
    if os.environ.get("MURMURY_TEST_SETTINGS"):  # tests write to their own preferences, never the user's
        return QSettings("Murmury-test", "Murmury-test")
    settings = QSettings("Murmury", "Murmury")
    if not settings.allKeys():
        old = QSettings("call-copilot", "call-copilot")
        for key in old.allKeys():
            settings.setValue(key, old.value(key))
    return settings


TOUR = [
    ("Your calls", "Each call keeps its documents, description and settings, so you can open it again before "
                   "the next meeting. Press + to start one. It is kept by itself, no save button."),
    ("Documents", "Drop the PDFs, spreadsheets and notes for this call. Murmury answers only from them, "
                  "and reads every page for every answer."),
    ("What is the call", "Say who you are talking to and what they will ask, in a sentence or two. "
                         "The clearer this is, the better the answers."),
    ("Your AI", "Pick a service, paste its API key and press List models. Gemini, Groq and OpenRouter have "
                "free tiers. The key stays in your Mac's Keychain."),
    ("Answer style", "Choose how long answers are and how they sound. Add your own rules under How to answer, "
                     "and watch the preview change as you go."),
    ("Start Listening", "A small window floats over your call and whispers an answer when someone asks you "
                        "something. Screen sharing cannot see it, and nothing is saved."),
]


class Tour(QDialog):
    """The first-run guide: one card per part of the setup screen, Back / Next, skippable."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setStyleSheet(theme.fill(STYLE))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame(objectName="panel")
        panel.setFixedWidth(420)
        outer.addWidget(panel)
        box = QVBoxLayout(panel)
        box.setContentsMargins(24, 20, 24, 18)
        box.setSpacing(8)
        self.counter = QLabel("", objectName="muted")
        self.heading = QLabel("", objectName="title")
        self.body = QLabel("", objectName="tour_body", wordWrap=True)
        self.body.setMinimumHeight(56)
        self.dots = QLabel("")
        self.dots.setTextFormat(Qt.TextFormat.RichText)
        for w in (self.counter, self.heading, self.body, self.dots):
            box.addWidget(w)
        box.addSpacing(6)
        row = QHBoxLayout()
        skip = QPushButton("Skip", objectName="link", cursor=Qt.CursorShape.PointingHandCursor)
        skip.clicked.connect(self.accept)
        row.addWidget(skip)
        row.addStretch(1)
        self.back = QPushButton("Back", objectName="cancel")
        self.back.clicked.connect(lambda: self.go(-1))
        self.next = QPushButton("Next", objectName="start")
        self.next.clicked.connect(lambda: self.go(1))
        self.next.setDefault(True)
        row.addWidget(self.back)
        row.addWidget(self.next)
        box.addLayout(row)
        self.step = 0
        self.show_step()

    def go(self, delta: int) -> None:
        if self.step + delta >= len(TOUR):
            self.accept()
            return
        self.step = max(0, self.step + delta)
        self.show_step()

    def show_step(self) -> None:
        title, text = TOUR[self.step]
        colours = theme.palette()
        self.counter.setText(f"Welcome to Murmury · {self.step + 1} of {len(TOUR)}")
        self.heading.setText(title)
        self.body.setText(text)
        self.dots.setText(" ".join(f'<span style="color:{colours["accent"] if i == self.step else colours["faint"]};">●</span>'
                                   for i in range(len(TOUR))))
        self.back.setVisible(self.step > 0)
        self.next.setText("Get started" if self.step == len(TOUR) - 1 else "Next")
        self.adjustSize()

    def showEvent(self, event):
        parent = self.parentWidget()
        if parent:  # centred over the setup window
            self.adjustSize()
            self.move(parent.frameGeometry().center() - self.rect().center())
        super().showEvent(event)


class SetupDialog(QDialog):
    WIDTH = 1000  # the usual width; the green button fills the screen
    checked = Signal(str, dict)  # a key check finished in the background: (provider id, result)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Murmury")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.apply_theme()
        theme.watch(self.apply_theme)
        self.setAcceptDrops(True)
        self.settings = settings_store()
        self.paths_: list[str] = []
        self._drag: QPoint | None = None

        self.outer = outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)  # the window is always as tall as its content
        self.panel = panel = QFrame(objectName="panel")
        panel.setFixedWidth(self.WIDTH)
        outer.addWidget(panel)
        self._zoomed_from: QRect | None = None
        box = QVBoxLayout(panel)
        box.setContentsMargins(20, 12, 20, 18)
        box.setSpacing(6)

        lights = TrafficLights()
        lights.close_clicked.connect(self.reject)
        lights.minimize_clicked.connect(self.minimize)
        lights.zoom_clicked.connect(self.toggle_zoom)
        # one title bar, as macOS windows have: traffic lights, then the app's name
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(lights)
        bar.addSpacing(10)
        bar.addWidget(QLabel("Murmury", objectName="bar_title"))
        bar.addStretch(1)
        helper = QPushButton("?", objectName="help", cursor=Qt.CursorShape.PointingHandCursor)
        helper.setToolTip("How Murmury works")
        helper.clicked.connect(self.show_tour)
        bar.addWidget(helper)
        bar.addSpacing(4)
        bar.addWidget(AppearanceButton())
        box.addLayout(bar)
        box.addSpacing(10)
        # two pages: the list of calls, and one call
        self.pages = QStackedWidget()
        box.addWidget(self.pages)
        self.pages.addWidget(self.build_home())
        editor = QWidget()
        ebox = QVBoxLayout(editor)
        ebox.setContentsMargins(0, 0, 0, 0)
        ebox.setSpacing(6)
        self.pages.addWidget(editor)
        self.current_call: str | None = None
        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        back = QPushButton("‹", objectName="back", cursor=Qt.CursorShape.PointingHandCursor)
        back.setToolTip("Back to your calls (this call is kept)")
        back.clicked.connect(self.back_to_calls)
        top_row.addWidget(back)
        self.call_name = QLineEdit(objectName="call_name", placeholderText="Name this call", maxLength=60)
        self.call_name.textChanged.connect(lambda _: self.update_save_state())
        top_row.addWidget(self.call_name, 1)
        self.call_note = QLabel("", objectName="muted")
        top_row.addWidget(self.call_note)
        self.save_state = QLabel("", objectName="muted")
        self.save_state.setTextFormat(Qt.TextFormat.RichText)
        top_row.addWidget(self.save_state)
        self.save_btn = QPushButton("Save", objectName="save", cursor=Qt.CursorShape.PointingHandCursor)
        self.save_btn.setToolTip("Keep this call as it is now (it is also kept when you go back or start)")
        self.save_btn.clicked.connect(self.save_now)
        top_row.addWidget(self.save_btn)
        self._saved_state: dict | None = None
        self.delete_call_btn = QPushButton("Delete call", objectName="link", cursor=Qt.CursorShape.PointingHandCursor)
        self.delete_call_btn.clicked.connect(self.delete_call)
        top_row.addWidget(self.delete_call_btn)
        ebox.addLayout(top_row)
        ebox.addSpacing(8)

        columns = QHBoxLayout()
        columns.setSpacing(24)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(6)
        right.setSpacing(6)
        columns.addLayout(left, 53)
        columns.addLayout(right, 47)
        ebox.addLayout(columns)

        # left: documents
        dhead = QHBoxLayout()
        dhead.addWidget(QLabel("Documents", objectName="section"))
        dhead.addWidget(QLabel("Murmury answers only from these", objectName="muted"))
        dhead.addStretch(1)
        self.add_more = QPushButton("+ Add", objectName="link", cursor=Qt.CursorShape.PointingHandCursor)
        self.add_more.clicked.connect(self.add_files)
        dhead.addWidget(self.add_more)
        left.addLayout(dhead)
        self.drop = DropZone()
        self.drop.clicked.connect(self.add_files)
        left.addWidget(self.drop)
        self.files = Group()
        left.addWidget(self.files)
        left.addSpacing(6)

        # left: the call
        left.addWidget(QLabel("What is the call", objectName="section"))
        self.situation = TextBox("Who you are talking to and what they will ask. e.g. A seed pitch to two investors "
                                 "who read our deck; expect questions on revenue, CAC and runway.", 400)
        self.situation.setToolTip("The clearer this is, the better the answers: it is read before every answer")
        left.addWidget(self.situation)
        left.addSpacing(4)
        call = Group()
        self.situation.changed.connect(self.update_save_state)
        self.vocabulary = QLineEdit(placeholderText="Names, products, acronyms")
        self.vocabulary.textChanged.connect(lambda _: self.update_save_state())
        suggest = QPushButton("Suggest", objectName="link", cursor=Qt.CursorShape.PointingHandCursor)
        suggest.setToolTip("Find names in the documents that speech recognition could mishear")
        suggest.clicked.connect(self.suggest)
        call.add("Names to hear right", self.vocabulary, suggest, stretch=True)
        self.provider = QComboBox()
        for p in providers.PROVIDERS:
            self.provider.addItem(p.name, p.id)
        self.provider.setToolTip("Answers come from your own account with this service, billed by them, "
                                 "or from a model you run yourself (Ollama, LM Studio), on this Mac or another computer")
        self.provider.currentIndexChanged.connect(lambda _: self.provider_changed())
        self.backend_hint = ""
        call.add("AI service", self.provider)
        self.conn_label = QLabel("", objectName="muted")
        self.conn_label.setTextFormat(Qt.TextFormat.RichText)
        self.conn_label.setWordWrap(True)
        self.key_field = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.key_field.returnPressed.connect(self.save_key)
        # Ollama / LM Studio: where the server is. Empty means this Mac.
        self.address_field = QLineEdit()
        self.address_field.setToolTip("Leave empty for this Mac. To use another computer on your network, enter its "
                                      "address, like http://mac-mini.local:11434, and press Return")
        self.address_field.returnPressed.connect(self.check_connection)
        self.conn_links: list[QPushButton] = []
        self.conn_box = QWidget()
        crow = QHBoxLayout(self.conn_box)
        crow.setContentsMargins(0, 0, 0, 0)
        crow.setSpacing(6)
        crow.addWidget(self.conn_label, 1)
        crow.addWidget(self.key_field, 1)
        crow.addWidget(self.address_field, 1)
        self.conn_actions = QHBoxLayout()
        self.conn_actions.setSpacing(2)
        crow.addLayout(self.conn_actions)
        call.add("Connection", self.conn_box, stretch=True)
        self.connected = False
        self.checked.connect(self.show_check)
        self.model = QComboBox()
        self.model.currentIndexChanged.connect(lambda _: self.update_save_state())
        self.model.setMinimumWidth(240)
        self.model.setToolTip("The list comes from the service, so new models appear by themselves")
        self.model.setPlaceholderText("Add your key to see the models")
        list_models = QPushButton("List models", objectName="link", cursor=Qt.CursorShape.PointingHandCursor)
        list_models.setToolTip("Ask the service which models your key can use (a free call)")
        list_models.clicked.connect(self.list_models)
        call.add("Answer model", self.model, list_models)
        self.prepare_on = Switch()
        self.prepare_on.setToolTip("Takes about 30 seconds and costs about $0.5 for 20 questions (estimate).")
        self.prepare_n = QSpinBox(minimum=5, maximum=40, value=20, suffix=" questions")
        self.prepare_on.toggled.connect(self.prepare_n.setEnabled)
        call.add("Prepare likely questions first", self.prepare_n, self.prepare_on)
        left.addWidget(call)
        left.addStretch(1)

        # right: answer style, always open
        shead = QHBoxLayout()
        shead.addWidget(QLabel("Answer style", objectName="section"))
        self.style_summary = QLabel("", objectName="muted")
        shead.addWidget(self.style_summary)
        shead.addStretch(1)
        self.reset = QPushButton("Reset", objectName="link", cursor=Qt.CursorShape.PointingHandCursor)
        self.reset.clicked.connect(lambda: self.set_style(Style()))
        shead.addWidget(self.reset)
        right.addLayout(shead)
        self.style_box = self.build_style()
        right.addWidget(self.style_box)
        right.addSpacing(4)
        right.addWidget(QLabel("How to answer", objectName="section"))
        self.extra = TextBox("Your rules for every answer. e.g. Amounts in € millions with one decimal. "
                             "Never promise dates.", 300, lines=2)
        self.extra.setToolTip("Sent with every answer, so keep it short")
        self.extra.changed.connect(self.style_changed)
        right.addWidget(self.extra)
        self.preview = QFrame(objectName="preview")
        pbox = QVBoxLayout(self.preview)
        pbox.setContentsMargins(12, 10, 12, 10)
        pbox.setSpacing(4)
        self.preview_say = QLabel("", objectName="preview_say", wordWrap=True)
        pbox.addWidget(self.preview_say)
        self.preview_lines = [QLabel("", objectName="preview_line", wordWrap=True, textFormat=Qt.TextFormat.RichText)
                              for _ in PREVIEW_LINES]
        for label in self.preview_lines:
            pbox.addWidget(label)
        right.addStretch(1)
        ebox.addSpacing(10)  # the preview runs under both columns
        ebox.addWidget(QLabel("Preview", objectName="section"))
        ebox.addWidget(self.preview)
        ebox.addSpacing(10)

        foot = QHBoxLayout()
        self.summary = QLabel("", objectName="muted")
        foot.addWidget(self.summary, 1)
        cancel, self.start = QPushButton("Cancel", objectName="cancel"), QPushButton("Start Listening", objectName="start")
        cancel.clicked.connect(self.reject)
        self.start.clicked.connect(self.accept)
        self.start.setDefault(True)
        foot.addWidget(cancel)
        foot.addWidget(self.start)
        ebox.addLayout(foot)

        self.restore()
        self.fill_home()
        self.pages.setCurrentIndex(0)
        self.refresh()
        if self.settings.value("tour_done") != "true":  # the first time: explain the screen
            QTimer.singleShot(400, self.show_tour)
        self.setFocus()  # no field starts highlighted

    def show_tour(self) -> None:
        Tour(self).exec()
        self.settings.setValue("tour_done", "true")

    def toggle_zoom(self) -> None:
        """Green: fill the screen (the menu bar and Dock stay visible); again: back to the usual size and place."""
        if self._zoomed_from is None:
            self._zoomed_from = self.geometry()
            area = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
            self.outer.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
            self.setMinimumSize(0, 0)  # the fixed-size layout had pinned the window's own limits
            self.setMaximumSize(16777215, 16777215)
            self.panel.setFixedSize(area.size())
            self.setGeometry(area)
        else:
            back, self._zoomed_from = self._zoomed_from, None
            self.panel.setMinimumSize(0, 0)
            self.panel.setMaximumSize(16777215, 16777215)
            self.panel.setFixedWidth(self.WIDTH)
            self.outer.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
            self.adjustSize()
            self.move(back.topLeft())

    def minimize(self) -> None:
        """Yellow: to the Dock. A frameless window needs the 'miniaturizable' flag set on its macOS window."""
        try:
            import objc
            from AppKit import NSWindowStyleMaskMiniaturizable
            window = objc.objc_object(c_void_p=int(self.winId())).window()
            window.setStyleMask_(window.styleMask() | NSWindowStyleMaskMiniaturizable)
            window.miniaturize_(None)
        except Exception:
            self.showMinimized()

    def apply_theme(self) -> None:
        self.setStyleSheet(theme.fill(STYLE))
        theme.refresh_native(self)
        if hasattr(self, "conn_label"):
            self.check_connection()  # its coloured dot comes from the palette
        self.update()

    # window: frameless, dragged from anywhere that is not a control
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, event):
        self._drag = None

    # documents
    def add_paths(self, paths: list[str]) -> None:
        for p in paths:
            path = Path(p)
            if path.suffix.lower() in SUFFIXES and path.is_file() and str(path) not in self.paths_:
                self.paths_.append(str(path))
        self.refresh()

    def remove_path(self, path: str) -> None:
        self.paths_.remove(path)
        self.refresh()

    def add_files(self) -> None:
        start = self.settings.value("last_dir", str(Path.home()))
        files, _ = QFileDialog.getOpenFileNames(self, "Documents for this call", start, TYPES)
        if files:
            self.settings.setValue("last_dir", str(Path(files[0]).parent))
            self.add_paths(files)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_paths([u.toLocalFile() for u in event.mimeData().urls()])

    def suggest(self) -> None:
        if self.paths_:
            self.vocabulary.setText(suggest_vocabulary([Path(p) for p in self.paths_]))

    # state
    def paths(self) -> list[str]:
        return list(self.paths_)

    def refresh(self) -> None:
        for row in self.files.rows:  # rebuild the file rows
            row.deleteLater()
        while self.files.box.count():
            item = self.files.box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.files.rows = []
        for p in self.paths_:
            path = Path(p)
            size = path.stat().st_size
            glyph = QLabel()
            glyph.setPixmap(icon(FILE_SVG, 16))
            name = QLabel(path.name, objectName="file")
            name.setToolTip(str(path))
            label = QWidget()
            lrow = QHBoxLayout(label)
            lrow.setContentsMargins(0, 0, 0, 0)
            lrow.setSpacing(8)
            lrow.addWidget(glyph)
            lrow.addWidget(name)
            remove = QPushButton("✕", objectName="remove", cursor=Qt.CursorShape.PointingHandCursor)
            remove.setToolTip("Remove")
            remove.clicked.connect(lambda _=False, q=p: self.remove_path(q))
            self.files.add(label, QLabel(f"{size / 1e6:.1f} MB" if size > 1e5 else f"{size / 1e3:.0f} KB",
                                         objectName="muted"), remove)
        n = len(self.paths_)
        self.drop.setVisible(n == 0)
        self.files.setVisible(n > 0)
        self.add_more.setVisible(n > 0)
        connected = getattr(self, "connected", False)
        has_model = self.model.currentData() is not None if hasattr(self, "model") else False
        self.start.setEnabled(n > 0 and connected and has_model)
        self.summary.setText("Add at least one document" if n == 0 else
                             "Connect an AI service to start" if not (connected and has_model)
                             else f"{n} document{'s' if n > 1 else ''}")
        self.update_save_state()
        if self._zoomed_from is None:  # zoomed, the window keeps the screen's size
            self.adjustSize()

    def restore(self) -> None:
        for key in ("docs", "vocabulary"):  # remembered by earlier versions: forget them
            self.settings.remove(key)
        if text := self.settings.value("situation"):
            self.situation.setText(text)
        self.prepare_on.setChecked(self.settings.value("prepare_on", "false") == "true")
        self.prepare_n.setValue(int(self.settings.value("prepare_n", 20)))
        self.prepare_n.setEnabled(self.prepare_on.isChecked())
        self.set_style(load_style(self.settings))
        self.provider.blockSignals(True)
        self.provider.setCurrentIndex(max(self.provider.findData(default_provider(self.settings)), 0))
        self.provider.blockSignals(False)
        self.provider_changed()

    def config(self) -> Config:
        config = Config(self.paths(), self.situation.text().strip() or SITUATIONS[0],
                        self.vocabulary.text().strip(),
                        self.prepare_n.value() if self.prepare_on.isChecked() else 0,
                        self.model.currentData(), self.current_style(), self.provider_id())
        if not providers.provider(config.provider).key_required:
            config.address = self.address_field.text().strip()
        if config.provider != "anthropic":
            config.prepare = 0  # preparing answers uses Anthropic's separate question check
        save_style(self.settings, config.style)
        for key, value in (("situation", config.situation), (f"model_{config.provider}", config.model),
                           ("provider", config.provider),
                           *([(f"address_{config.provider}", config.address)]
                             if not providers.provider(config.provider).key_required else []),
                           ("prepare_on", str(self.prepare_on.isChecked()).lower()),
                           ("prepare_n", self.prepare_n.value())):
            self.settings.setValue(key, value)
        self.persist_call()  # Start Listening keeps the call, like going back does
        return config

    # calls: each keeps its name, document locations (not copies) and settings, in the app's preferences.
    # No save button: a call is kept when you go back to the list or start listening, like a note in Notes.
    def saved_calls(self) -> list[dict]:
        try:
            calls = json.loads(self.settings.value("calls", "[]"))
        except (TypeError, ValueError):
            return []
        for call in calls:
            call.setdefault("id", call.get("name") or uuid4().hex)  # saved before calls had ids
        return calls

    def build_home(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(QLabel("Your calls", objectName="title"))
        head.addStretch(1)
        self.new_btn = QPushButton("+  New call", objectName="start", cursor=Qt.CursorShape.PointingHandCursor)
        self.new_btn.clicked.connect(self.new_call)
        head.addWidget(self.new_btn)
        v.addLayout(head)
        holder = QWidget()
        self.call_list = QVBoxLayout(holder)
        self.call_list.setContentsMargins(0, 0, 0, 0)
        self.call_list.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(holder)
        v.addWidget(scroll, 1)
        return page

    def fill_home(self) -> None:
        while self.call_list.count():
            item = self.call_list.takeAt(0)
            if widget := item.widget():
                widget.setParent(None)  # gone now, not at the next turn of the event loop
                widget.deleteLater()
        calls = self.saved_calls()
        self.new_btn.setVisible(bool(calls))
        if not calls:  # first time: one big +
            self.call_list.addStretch(1)
            plus = QPushButton("+", objectName="plus", cursor=Qt.CursorShape.PointingHandCursor)
            plus.setToolTip("New call")
            plus.clicked.connect(self.new_call)
            self.call_list.addWidget(plus, 0, Qt.AlignmentFlag.AlignHCenter)
            self.call_list.addSpacing(6)
            self.call_list.addWidget(QLabel("No calls yet", objectName="section", alignment=Qt.AlignmentFlag.AlignCenter))
            self.call_list.addWidget(QLabel("Create one: add the documents, say what the call is, pick your AI.",
                                            objectName="muted", alignment=Qt.AlignmentFlag.AlignCenter))
            self.call_list.addStretch(2)
            return
        if int(self.settings.value("answered_calls", 0) or 0) >= 1 and self.settings.value("star_asked") != "true":
            self.call_list.addWidget(self.star_banner())
        for call in calls:
            row = CallRow(call)
            row.clicked.connect(self.open_call)
            self.call_list.addWidget(row)
        self.call_list.addStretch(1)

    def star_banner(self) -> QFrame:
        """Asked once, after the first call Murmury answered in: a star helps other people find the project."""
        banner = QFrame(objectName="star")
        row = QHBoxLayout(banner)
        row.setContentsMargins(14, 10, 8, 10)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(QLabel("Did the elf help?", objectName="call_title"))
        text.addWidget(QLabel("Murmury is free and open source. A star on GitHub helps other people find it.",
                              objectName="muted"))
        row.addLayout(text, 1)

        def done(open_page: bool) -> None:
            self.settings.setValue("star_asked", "true")
            if open_page:
                QDesktopServices.openUrl(QUrl(REPO_URL))
            self.fill_home()

        star = QPushButton("★  Star on GitHub", objectName="start", cursor=Qt.CursorShape.PointingHandCursor)
        star.clicked.connect(lambda: done(True))
        close = QPushButton("✕", objectName="close", cursor=Qt.CursorShape.PointingHandCursor)
        close.setToolTip("Don't ask again")
        close.clicked.connect(lambda: done(False))
        row.addWidget(star)
        row.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        return banner

    def new_call(self) -> None:
        self.current_call = None
        self.call_name.setText("")
        self.paths_ = []
        self.situation.setText("")
        self.vocabulary.setText("")
        self.set_style(Style())  # a new call starts from the standard style, without another call's rules
        self.call_note.setText("")
        self.delete_call_btn.setVisible(False)
        self._saved_state = None
        self.pages.setCurrentIndex(1)
        self.refresh()
        self.call_name.setFocus()

    def open_call(self, call_id: str) -> None:
        call = next((c for c in self.saved_calls() if c["id"] == call_id), None)
        if call is None:
            return
        self.current_call = call_id
        self.call_name.setText(call.get("name", ""))
        self.paths_ = [d for d in call.get("docs", []) if Path(d).exists()]
        missing = len(call.get("docs", [])) - len(self.paths_)
        self.call_note.setText(f"{missing} file{'s' if missing > 1 else ''} moved or deleted" if missing else "")
        self.situation.setText(call.get("situation", ""))
        self.vocabulary.setText(call.get("vocabulary", ""))
        if style := call.get("style"):
            self.set_style(Style(**{k: v for k, v in style.items() if k in STYLE_KEYS}))
        provider_id = providers.provider(call.get("provider")).id
        if call.get("model"):
            self.settings.setValue(f"model_{provider_id}", call["model"])  # preselected when the list arrives
        if provider_id != self.provider_id():
            self.provider.setCurrentIndex(max(self.provider.findData(provider_id), 0))
        else:
            self.check_connection()
        self.delete_call_btn.setVisible(True)
        self.pages.setCurrentIndex(1)
        self._saved_state = self.call_state()
        self.refresh()

    def call_state(self) -> dict:
        """What a saved call holds, to tell whether the screen differs from what was saved."""
        return {"name": self.call_name.text().strip(), "docs": list(self.paths_),
                "situation": self.situation.text().strip(), "vocabulary": self.vocabulary.text().strip(),
                "provider": self.provider_id(), "model": self.model.currentData(), "style": asdict(self.current_style())}

    def update_save_state(self) -> None:
        if not hasattr(self, "save_btn"):
            return
        now, saved = self.call_state(), self._saved_state
        if saved is not None and now["model"] is None:  # the model list is still loading: not a change
            now["model"] = saved.get("model")
        empty = not (now["name"] or now["docs"] or now["situation"])
        if saved is None and empty:
            changed, text = False, ""
        elif saved is None:
            changed, text = True, "Not saved yet"
        elif now != saved:
            changed, text = True, "Unsaved changes"
        else:
            accent = theme.palette()["accent"]
            changed, text = False, f'<span style="color:{accent};">●</span> Saved'
        self.save_state.setText(text)
        self.save_btn.setEnabled(changed)

    def save_now(self) -> None:
        self.persist_call()
        self.update_save_state()

    def persist_call(self) -> None:
        """Keep the open call. A new call nobody touched is not kept."""
        name = self.call_name.text().strip()
        if self.current_call is None and not (name or self.paths_ or self.situation.text().strip()):
            return
        if not name:
            name = " ".join(self.situation.text().split()[:6]).rstrip(".,;") or "Untitled call"
            self.call_name.setText(name)
        call_id = self.current_call or uuid4().hex
        calls = [c for c in self.saved_calls() if c["id"] != call_id]
        calls.insert(0, {"id": call_id, "name": name[:60], "docs": list(self.paths_),
                         "situation": self.situation.text().strip(), "vocabulary": self.vocabulary.text().strip(),
                         "provider": self.provider_id(), "model": self.model.currentData(),
                         "style": asdict(self.current_style())})
        self.settings.setValue("calls", json.dumps(calls))
        self.current_call = call_id
        self._saved_state = self.call_state()

    def back_to_calls(self) -> None:
        self.persist_call()
        self.fill_home()
        self.pages.setCurrentIndex(0)
        self.refresh()

    def delete_call(self) -> None:
        if self.current_call:
            self.settings.setValue("calls", json.dumps([c for c in self.saved_calls() if c["id"] != self.current_call]))
        self.current_call = None
        self.fill_home()
        self.pages.setCurrentIndex(0)
        self.refresh()

    def provider_id(self) -> str:
        return self.provider.currentData() or providers.DEFAULT

    def provider_changed(self) -> None:
        """New service: its own key, its own models. Preparing answers needs Anthropic's question check."""
        p = providers.provider(self.provider_id())
        anthropic = p.id == "anthropic"
        # measured 8 October 2026 on a 70-page plan: first text 0.64-0.80 s with Claude Sonnet by API
        self.backend_hint = "~0.8 s with Claude Sonnet" if anthropic else p.free
        self.key_field.setPlaceholderText(f"Paste your {p.name.split(' ·')[0]} key ({p.key_hint})")
        self.address_field.setPlaceholderText(f"This Mac ({p.base_url.removesuffix('/v1')})" if p.base_url else "")
        self.address_field.setText(str(self.settings.value(f"address_{p.id}") or "") if not p.key_required else "")
        self.prepare_on.setEnabled(anthropic)
        self.prepare_n.setEnabled(anthropic and self.prepare_on.isChecked())
        self.prepare_on.setToolTip("Takes about 30 seconds and costs about $0.5 for 20 questions (estimate)."
                                   if anthropic else "Available with Anthropic: other services write every answer live.")
        self.model.clear()
        self.check_connection()

    # connection: the user's key for the chosen service
    def set_connection(self, text: str, ok: bool | None, actions: list[tuple[str, object]] = (),
                       key_field: bool = False) -> None:
        colours = theme.palette()
        mark = {True: f'<span style="color:{colours["accent"]};">●</span> ', False: f'<span style="color:{colours["danger"]};">●</span> ',
                None: ""}[ok]
        hint = f' <span style="color:{colours["tertiary"]};">· {self.backend_hint}</span>' if ok and self.backend_hint else ""
        self.conn_label.setText(mark + text + hint)
        self.key_field.setVisible(key_field)
        self.address_field.setVisible(not providers.provider(self.provider_id()).key_required)
        for b in self.conn_links:  # out of the layout now, not at the next event loop turn
            b.hide()
            self.conn_actions.removeWidget(b)
            b.deleteLater()
        self.conn_links = []
        for label, slot in actions:
            b = QPushButton(label, objectName="link", cursor=Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            self.conn_actions.addWidget(b)
            self.conn_links.append(b)
        self.connected = bool(ok)
        self.refresh()

    def check_connection(self) -> None:
        """Check the provider and load its models in the background; local servers do not need a key."""
        import threading
        p = providers.provider(self.provider_id())
        key, source = providers.api_key(p.id)
        if p.key_required and not key:
            self.model.clear()  # no key, no models: never show a list the key cannot back
            self.model.setPlaceholderText("Add your key to see the models")
            self.set_connection("", None, [("Save", self.save_key),
                                           ("Get a key", lambda: QDesktopServices.openUrl(QUrl(p.key_url)))],
                                key_field=True)
            return
        address = self.address_field.text().strip() if not p.key_required else ""
        try:
            providers.normalize_address(address, "")
        except ValueError as error:  # not an http(s) address: say so before asking the network
            self.model.clear()
            self.model.setPlaceholderText("Fix the address to see the models")
            self.set_connection(str(error), False)
            return
        self.model.setPlaceholderText("Loading local models…" if not p.key_required else "Loading the models…")
        self.set_connection(f"Checking {p.name.split(' ·')[0]}…" if not p.key_required else
                            f"Checking your {p.name.split(' ·')[0]} key…", None)

        def run() -> None:
            try:
                models = providers.list_models(p.id, key, address)
                self.checked.emit(p.id, {"ok": True, "models": models, "keychain": source == "Keychain",
                                         "suggested": providers.suggest(p.id, models)})
            except Exception as error:
                self.checked.emit(p.id, {"ok": False, "error": type(error).__name__,
                                         "keychain": source == "Keychain"})
        threading.Thread(target=run, daemon=True).start()

    def show_check(self, provider_id: str, result: dict) -> None:
        if provider_id != self.provider_id():
            return  # the choice changed while checking
        service = providers.provider(provider_id)
        name = service.name.split(" ·")[0]
        if not result.get("ok"):
            self.model.setPlaceholderText("Start the local server to see its models" if not service.key_required
                                          else "Fix the key to see the models")
            message = (f"{name} did not answer: is it running? ({result.get('error', '')[:60]})" if not service.key_required
                       else f"{name} key rejected: {result.get('error', '')[:60]}")
            self.set_connection(message, False,
                                [("Change", self.remove_key)] if result.get("keychain") else [])
            return
        models, suggested = result.get("models", []), result.get("suggested")
        saved = self.settings.value(f"model_{provider_id}")
        self.model.blockSignals(True)
        self.model.clear()
        for model_id in ([suggested] if suggested else []) + [m for m in models if m != suggested]:
            self.model.addItem(f"{model_id}  · suggested" if model_id == suggested else model_id, model_id)
        self.model.setCurrentIndex(max(self.model.findData(saved if saved in models else suggested), 0))
        self.model.blockSignals(False)
        if not models:
            message = (f"{name} is available, but it has no chat models" if not service.key_required
                       else f"{name} key works, but it has no chat models")
            self.set_connection(message, False,
                                [("Change", self.remove_key)] if result.get("keychain") else [])
            return
        status = f"{name} available" if not service.key_required else f"{name} key works"
        self.set_connection(f"{status} · {len(models)} model{'s' if len(models) != 1 else ''}", True,
                            [("Remove", self.remove_key)] if result.get("keychain") else [])

    def save_key(self) -> None:
        p = providers.provider(self.provider_id())
        if not p.key_required:
            return
        key = self.key_field.text().strip()
        if not key:
            return
        if (p.id == "anthropic") != key.startswith("sk-ant-"):  # an Anthropic key in the wrong place, or the reverse
            self.set_connection("That looks like an Anthropic key: choose Anthropic above" if p.id != "anthropic"
                                else "That is not an Anthropic key (they start with sk-ant-)", False,
                                [("Save", self.save_key)], key_field=True)
            return
        providers.save_api_key(p.id, key)
        self.key_field.clear()
        self.check_connection()

    def list_models(self) -> None:
        """A key just pasted is saved first; then the service is asked again for its models."""
        if not self.key_field.isHidden() and self.key_field.text().strip():
            self.save_key()
        else:
            self.check_connection()

    def remove_key(self) -> None:
        providers.save_api_key(self.provider_id(), None)
        self.model.clear()
        self.check_connection()

    # answer style
    def build_style(self) -> QWidget:
        group = Group()
        self.format = Segmented(FORMAT_LABELS)
        self.format.setToolTip("Talking points: sentences to say and talk around. Key facts: label and figure. "
                               "Script: the whole answer to read almost word for word.")
        self.format.changed.connect(lambda _: self.style_changed())
        group.add("Format", self.format)
        self.preset = Segmented([(name, name) for name in PRESETS])
        self.preset.changed.connect(self.apply_preset)
        group.add("Length", self.preset)
        self.tone = Segmented(TONE_LABELS)
        self.tone.changed.connect(lambda _: self.style_changed())
        group.add("Tone", self.tone)
        self.say_words = Slider(5, 30, "word", "words")
        group.add("Main sentence", self.say_words)
        self.lines = Slider(1, 6, "line", "lines")
        group.add("Lines under it", self.lines)
        self.line_words = Slider(4, 25, "word", "words")
        group.add("Each line at most", self.line_words)
        self.numbers = Slider(0, 4, "number", "numbers")
        group.add("Numbers per line", self.numbers)
        for slider in (self.say_words, self.lines, self.line_words, self.numbers):
            slider.valueChanged.connect(lambda _: self.style_changed())
        self.language = QComboBox()
        for label, value in LANGUAGES:
            self.language.addItem(label, value)
        self.language.currentIndexChanged.connect(self.style_changed)
        self.sources = Switch()
        self.sources.setToolTip("Page, table or cell each line comes from")
        self.sources.toggled.connect(self.style_changed)
        group.add("Language", self.language, QLabel("  "), QLabel("Sources", objectName="muted"), self.sources)
        return group

    def apply_preset(self, name: str) -> None:
        current, p = self.current_style(), PRESETS[name]
        self.set_style(Style(p.say_words, p.lines, p.line_words, p.numbers, current.sources, current.tone,
                             current.language, current.extra, current.format))

    def set_style(self, style: Style) -> None:
        self._loading = True
        self.say_words.setValue(style.say_words)
        self.lines.setValue(style.lines)
        self.line_words.setValue(style.line_words)
        self.numbers.setValue(style.numbers)
        self.sources.setChecked(style.sources)
        self.tone.set_value(style.tone)
        self.format.set_value(style.format)
        self.language.setCurrentIndex(max(self.language.findData(style.language), 0))
        self.extra.setText(style.extra)
        self._loading = False
        self.style_changed()

    def current_style(self) -> Style:
        return Style(self.say_words.value(), self.lines.value(), self.line_words.value(), self.numbers.value(),
                     self.sources.isChecked(), self.tone.value() or "confident", self.language.currentData(),
                     self.extra.text().strip(), self.format.value() or "talking")

    def style_changed(self) -> None:
        if getattr(self, "_loading", False):
            return
        style = self.current_style()
        shape = (style.say_words, style.lines, style.line_words, style.numbers)
        name = next((n for n, p in PRESETS.items() if (p.say_words, p.lines, p.line_words, p.numbers) == shape),
                    "Custom")
        self.preset.set_value(name)
        tone = dict((v, label) for label, v in TONE_LABELS)[style.tone]
        form = dict((v, label) for label, v in FORMAT_LABELS).get(style.format, "Talking points")
        self.style_summary.setText(f"{form}, {name.lower()}, {tone.lower()}")
        self.style_summary.setStyleSheet("")
        self.update_save_state()
        self.update_preview(style)

    def update_preview(self, style: Style) -> None:
        """The example answer, cut to the chosen length: what a card will look like."""
        words = PREVIEW_SAY.split()
        say = " ".join(words[:style.say_words]).rstrip(",;") + ("…" if len(words) > style.say_words else "")
        self.preview_say.setText(say)
        colours = theme.palette()
        samples = PREVIEW_FACTS if style.format == "facts" else PREVIEW_LINES
        parts = []
        for i, (label, (text, source)) in enumerate(zip(self.preview_lines, samples)):
            full = text.split()
            body = " ".join(full[:style.line_words]) + ("…" if len(full) > style.line_words else "")
            tag = (f' <span style="color:{colours["tag_fg"]}; background:{colours["tag_bg"]};">&nbsp;{source}&nbsp;</span>'
                   if style.sources else "")
            if style.format == "facts" and ":" in body:
                head, rest = body.split(":", 1)
                body_html = f"<b>{html_escape(head)}:</b>{html_escape(rest)}"
            else:
                body_html = html_escape(body)
            if i < style.lines:
                parts.append(body_html + ("" if body.endswith(("…", ".")) else ".") + tag
                             if style.format == "script" else f"• {body_html}{tag}")
            label.setVisible(False)
        if style.format == "script":  # one paragraph, as the call window shows it
            self.preview_lines[0].setText(" ".join(parts))
            self.preview_lines[0].setVisible(bool(parts))
        else:
            for label, text in zip(self.preview_lines, parts):
                label.setText(text)
                label.setVisible(True)

STYLE_KEYS = ("say_words", "lines", "line_words", "numbers", "sources", "tone", "language", "extra", "format")


def load_style(settings: QSettings | None = None) -> Style:
    """The answer style chosen last time (the standard one the first time)."""
    settings = settings or settings_store()
    default, values = Style(), {}
    for key in STYLE_KEYS:
        raw = settings.value(f"style/{key}")
        if raw is None:
            continue
        kind = type(getattr(default, key))
        try:
            values[key] = (str(raw).lower() == "true") if kind is bool else kind(raw)
        except (TypeError, ValueError):
            continue
    return Style(**values)


def save_style(settings: QSettings, style: Style) -> None:
    for key in STYLE_KEYS:
        value = getattr(style, key)
        settings.setValue(f"style/{key}", str(value).lower() if isinstance(value, bool) else value)
