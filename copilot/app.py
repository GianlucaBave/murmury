
"""The floating window: always on top, movable and resizable, hidden from screen sharing.

    uv run python -m copilot.app --docs plan.pdf model.xlsx --situation "a seed pitch to an investor"

Without --docs, a file dialog asks for the documents. Nothing is saved.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from . import material
from . import providers
from .answer import PreparedCopilot
from .openai_copilot import OpenAICopilot
from .listen import StreamingTranscriber
from . import theme
from .chrome import AppearanceButton, TrafficLights
from .pipeline import respond
from .setup import settings_store

JOIN_SECONDS = 6.0

STYLE = """
#panel { background: $glass; border: 1px solid $panel_border; border-radius: 12px; }
QLabel { color: $text; }
#bar { color: $secondary; font-size: 11px; }
#heard { color: $secondary; font-size: 12px; border-left: 2px solid $accent; padding-left: 8px; }
#question { color: $text; font-size: 14px; font-weight: 600; }
#keys { color: $tertiary; font-size: 11px; }
QScrollArea, #cards { background: transparent; border: none; }
#card { background: $card; border: 1px solid $card_border; border-radius: 8px; }
#cardq { color: $secondary; font-size: 12px; font-weight: 400; border-left: 2px solid $quote_bar; padding-left: 8px; }
#carda { color: $text; font-size: 14px; }
#cardmeta { color: $tertiary; font-size: 11px; }
QLineEdit { background: $input; border: 1px solid $input_border; border-radius: 6px; color: $text; padding: 4px 8px; }
QPushButton { background: transparent; border: none; color: $secondary; font-size: 13px; padding: 0 4px; }
QPushButton:hover { color: $link; }
"""

REF = re.compile(r"\[([^\]]{1,60})\]\s*$")

MAX_LINES = 3
ANSWERED = threading.Event()
FORMAT = "talking"


def card_lines(text: str) -> list[str]:
    """The lines a card shows: the SAY line and at most MAX_LINES facts."""
    lines, say, facts = [], False, 0

    for line in text.splitlines():
        line = line.strip()

        if not line or not (
            line.upper().startswith("SAY:") or line[0] in "-•*"
        ):
            continue

        if line.upper().startswith("SAY:"):
            if say:
                continue
            say = True
        else:
            if facts >= (MAX_LINES if say else MAX_LINES + 1):
                break
            facts += 1

        lines.append(line)

    return lines


def answer_html(text: str) -> str:
    """The SAY line large and bold; the facts as bullets with their source."""
    c = theme.palette()
    head, items = "", []

    for line in card_lines(text):
        if line.upper().startswith("SAY:"):
            head = (
                f'<p style="font-size:15px; font-weight:600; '
                f'color:{c["text"]}; margin:0 0 6px 0;">'
                f'{html.escape(line[4:].strip(), quote=False)}</p>'
            )
            continue

        line = line.lstrip("-•* ").strip()
        ref = REF.search(line)
        body = html.escape(
            line[:ref.start()].strip() if ref else line
        )

        plain = html.unescape(body)
        label = re.match(
            r"^([A-Za-z0-9][\w /&'’-]{0,40}):\s",
            plain,
        )
        rest = plain[label.end():] if label else plain

        rest = html.escape(rest, quote=False)
        rest = re.sub(
            r"([€$£]?\d[\d.,]*\s?(?:%|×|x|m|bn|k|million|billion)?)",
            rf'<b style="color:{c["text"]};">\1</b>',
            rest,
            count=1,
        )

        body = (
            f'<b style="color:{c["text"]};">'
            f'{html.escape(label.group(1), quote=False)}:</b> '
            if label else ""
        ) + rest

        tag = (
            f' <span style="color:{c["tag_fg"]}; '
            f'background:{c["tag_bg"]}; font-size:11px;">'
            f'&nbsp;{html.escape(ref.group(1), quote=False)}&nbsp;</span>'
            if ref else ""
        )

        items.append((body, tag))

    if FORMAT == "script":
        text = " ".join(
            f"{body}{'' if body.rstrip().endswith(('.', '!', '?')) else '.'}{tag}"
            for body, tag in items
        )
        return head + (
            f'<p style="margin:0; color:{c["text"]}; '
            f'line-height:140%;">{text}</p>'
            if items else ""
        )

    rows = "".join(
        f'<li style="margin-bottom:4px; color:{c["text"]};">'
        f'{body}{tag}</li>'
        for body, tag in items
    )

    return head + (
        f'<ul style="margin-left:-20px; margin-top:0;">{rows}</ul>'
        if items else ""
    )


def force_light_appearance() -> None:
    """Murmury is designed light; native controls would turn dark in Dark Mode."""
    try:
        from AppKit import NSAppearance, NSApplication

        NSApplication.sharedApplication().setAppearance_(
            NSAppearance.appearanceNamed_("NSAppearanceNameAqua")
        )
    except Exception:
        pass


def configure_native_window(
    widget: QWidget,
    hide_from_capture: bool = True,
) -> bool:
    """Keep the window visible over other apps and hidden from screen capture."""
    try:
        import objc
        from AppKit import (
            NSFloatingWindowLevel,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowSharingNone,
            NSWindowSharingReadOnly,
        )

        window = objc.objc_object(
            c_void_p=int(widget.winId())
        ).window()

        window.setHidesOnDeactivate_(False)
        window.setLevel_(NSFloatingWindowLevel)

        window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        window.setSharingType_(
            NSWindowSharingNone
            if hide_from_capture
            else NSWindowSharingReadOnly
        )

        return window.sharingType() == NSWindowSharingNone

    except Exception:
        return False


class Bridge(QObject):
    status = Signal(str)
    heard = Signal(str)
    card = Signal(int, str)
    answer = Signal(int, str)
    meta = Signal(int, str)
    timing = Signal(str)


class Window(QWidget):
    def __init__(self, bridge: Bridge, ask):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.setWindowTitle("Murmury")
        self.resize(430, 330)

        self.drag: QPoint | None = None
        self.ask = ask

        panel = QFrame(self, objectName="panel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(panel)

        box = QVBoxLayout(panel)
        box.setContentsMargins(14, 10, 14, 8)
        box.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)

        lights = TrafficLights()
        lights.close_clicked.connect(QApplication.quit)
        lights.minimize_clicked.connect(self.toggle_compact)
        lights.zoom_clicked.connect(self.toggle_zoom)

        top.addWidget(lights)

        self.bar = QLabel("Starting…", objectName="bar")
        top.addWidget(self.bar, 1)
        top.addWidget(AppearanceButton())

        box.addLayout(top)

        self.compact, self.zoomed, self.normal_size = False, False, None

        self.heard = QLabel("", objectName="heard", wordWrap=True)
        self.heard.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.cards: dict[int, tuple[QFrame, QLabel, QLabel, QLabel]] = {}
        self.plain: dict[int, str] = {}

        holder = QWidget(objectName="cards")
        self.stack = QVBoxLayout(holder)
        self.stack.setContentsMargins(0, 0, 4, 0)
        self.stack.setSpacing(8)
        self.stack.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(holder)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.input = QLineEdit(
            placeholderText="Type a question and press Enter"
        )
        self.input.hide()
        self.input.returnPressed.connect(self.ask_typed)

        keys = QHBoxLayout()
        keys.addWidget(
            QLabel(
                "⌥Space ask · ⌥K clear · scroll for earlier answers",
                objectName="keys",
            ),
            1,
        )
        keys.addWidget(
            QSizeGrip(panel),
            0,
            Qt.AlignmentFlag.AlignBottom
            | Qt.AlignmentFlag.AlignRight,
        )

        box.addWidget(self.heard)
        box.addWidget(self.scroll, 1)
        box.addWidget(self.input)

        self.keys = QWidget()
        self.keys.setLayout(keys)
        keys.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.keys)

        self.apply_theme()
        theme.watch(self.apply_theme)

        QShortcut(
            QKeySequence("Alt+Space"),
            self,
            self.toggle_input,
        )
        QShortcut(
            QKeySequence("Alt+K"),
            self,
            self.clear,
        )

        bridge.status.connect(self.bar.setText)
        bridge.heard.connect(
            lambda t: self.heard.setText(f"them: {t}")
        )
        bridge.card.connect(self.on_card)
        bridge.answer.connect(self.on_answer)
        bridge.meta.connect(self.on_meta)
        bridge.timing.connect(
            lambda t: self.bar.setText(t)
        )

    def toggle_compact(self) -> None:
        """Fold to the status bar only; again to unfold."""
        self.compact = not self.compact

        for w in (self.heard, self.scroll, self.keys):
            w.setVisible(not self.compact)

        if self.compact:
            self.normal_size = self.size()
            self.setMinimumHeight(0)
            self.resize(self.width(), 44)
        elif self.normal_size:
            self.resize(self.normal_size)

    def toggle_zoom(self) -> None:
        """Grow to most of the screen height; again to go back."""
        if self.compact:
            self.toggle_compact()

        screen = self.screen().availableGeometry()

        if not self.zoomed:
            self.normal_size = self.size()
            self.resize(
                max(self.width(), 520),
                int(screen.height() * 0.8),
            )
            self.move(
                self.x(),
                screen.top() + int(screen.height() * 0.1),
            )
        elif self.normal_size:
            self.resize(self.normal_size)

        self.zoomed = not self.zoomed

    # Drag anywhere on the window.
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self.drag is not None:
            self.move(
                event.globalPosition().toPoint() - self.drag
            )

    def mouseReleaseEvent(self, event):
        self.drag = None

    MAX_CARDS = 30

    def apply_theme(self) -> None:
        self.setStyleSheet(theme.fill(STYLE))
        theme.refresh_native(self)

        for card, (_, _, label, _) in getattr(
            self, "cards", {}
        ).items():
            if self.plain.get(card):
                label.setText(answer_html(self.plain[card]))

    def on_card(self, card: int, question: str) -> None:
        if card not in self.cards:
            frame = QFrame(objectName="card")
            inner = QVBoxLayout(frame)
            inner.setContentsMargins(10, 8, 10, 8)
            inner.setSpacing(4)

            q, a, meta = (
                QLabel("", objectName="cardq", wordWrap=True),
                QLabel("", objectName="carda", wordWrap=True),
                QLabel("", objectName="cardmeta"),
            )

            a.setTextFormat(Qt.TextFormat.RichText)

            for label in (q, a):
                label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )

            copy = QPushButton("Copy")
            copy.setCursor(Qt.CursorShape.PointingHandCursor)
            copy.clicked.connect(
                lambda _=False, c=card: self.copy_card(c)
            )

            footer = QHBoxLayout()
            footer.addWidget(meta, 1)
            footer.addWidget(copy)

            inner.addWidget(q)
            inner.addSpacing(4)
            inner.addWidget(a)
            inner.addLayout(footer)

            self.stack.insertWidget(0, frame)
            self.cards[card] = (frame, q, a, meta)

            for old in sorted(self.cards)[
                :max(0, len(self.cards) - self.MAX_CARDS)
            ]:
                self.cards.pop(old)[0].deleteLater()

            self.scroll.verticalScrollBar().setValue(0)

        self.cards[card][1].setText(question)
        self.cards[card][2].setText("")

    def on_answer(self, card: int, text: str) -> None:
        if card in self.cards:
            self.cards[card][2].setText(answer_html(text))
            self.plain[card] = text

    def copy_card(self, card: int) -> None:
        if card in self.cards:
            question = self.cards[card][1].text()
            shown = "\n".join(
                card_lines(self.plain.get(card, ""))
            )

            QApplication.clipboard().setText(
                f"{question}\n{shown}".strip()
            )

            self.cards[card][3].setText(
                self.cards[card][3].text().split(" · copied")[0]
                + " · copied"
            )

    def on_meta(self, card: int, text: str) -> None:
        if card in self.cards:
            self.cards[card][3].setText(text)

    def toggle_input(self) -> None:
        self.input.setVisible(not self.input.isVisible())

        if self.input.isVisible():
            self.activateWindow()
            self.input.setFocus()

    def ask_typed(self) -> None:
        text = self.input.text().strip()

        if text:
            self.input.clear()
            self.input.hide()
            self.ask(text)

    def clear(self) -> None:
        self.heard.setText("")

        for frame, *_ in self.cards.values():
            frame.deleteLater()

        self.cards.clear()


RUNS: dict[int, int] = {}
CARDS = {"next": 0}


def new_card() -> int:
    CARDS["next"] += 1
    return CARDS["next"]


def run_answer(
    copilot: PreparedCopilot,
    bridge: Bridge,
    card: int,
    line: str,
    before: str,
    heard_at: float,
) -> None:
    run = RUNS[card] = RUNS.get(card, 0) + 1
    live = ""
    first = None

    for show in respond(copilot, line, before):
        if RUNS[card] != run:
            return

        if show.kind == "dropped":
            return

        if first is None:
            first = show.at - heard_at
            bridge.card.emit(card, line)
            ANSWERED.set()

        if show.kind == "prepared":
            bridge.answer.emit(card, show.text)

        elif show.kind == "live-chunk":
            live += show.text
            bridge.answer.emit(card, live)

        elif show.kind == "live-done":
            bridge.answer.emit(card, show.text)
            copilot.remember(line, show.text)

            bridge.meta.emit(
                card,
                f"{time.strftime('%H:%M')} · first text {first:.2f}s after transcript",
            )
            bridge.timing.emit("Listening · nothing saved")


def start(
    copilot_ready: threading.Event,
    holder: dict,
    bridge: Bridge,
    args,
) -> None:
    bridge.status.emit("Loading documents…")

    text = material.as_prompt(
        material.load([Path(p) for p in args.docs])
    )

    service = providers.provider(args.provider)

    try:
        if service.id == "anthropic":
            copilot = PreparedCopilot(
                text,
                situation=args.situation,
                model=args.model,
                style=args.style,
            )
        else:
            key = providers.api_key(service.id)[0]

            if service.key_required and not key:
                raise RuntimeError(
                    f"no {service.name} key: add one on the setup screen"
                )

            copilot = OpenAICopilot(
                text,
                args.situation,
                service,
                key or "local",
                args.model,
                args.style,
            )

    except Exception as error:
        bridge.status.emit(
            f"Could not reach the model: {str(error)[:120]}"
        )
        return

    bridge.status.emit(
        "Caching documents…"
        if service.id == "anthropic"
        else f"Connecting to {args.model}…"
    )

    try:
        usage = copilot.warm()
    except Exception as error:
        bridge.status.emit(
            f"Could not reach {service.name.split(' ·')[0]}: {str(error)[:120]}"
        )
        return

    if service.id == "anthropic":
        per_million = {
            "claude-sonnet-5-5": 4.0,
            "claude-haiku-4-5": 2.0,
        }.get(args.model)

        cost = (
            f" (${usage.cache_write * per_million / 1e6:.2f})"
            if per_million else ""
        )

        bridge.status.emit(
            f"{usage.cache_write + usage.cache_read:,} tokens cached{cost}"
        )

    else:
        bridge.status.emit(f"Ready · {args.model}")

        read = usage.input + usage.cache_read

        if (
            not service.key_required
            and 0 < read < len(copilot.system) / 6
        ):
            name, card = service.name.split(" ·")[0], new_card()

            bridge.card.emit(
                card,
                f"{name} cut your documents",
            )

            bridge.answer.emit(
                card,
                f"Only the last {read:,} tokens reached the model, "
                f"so answers will miss most of them. "
                f"Raise the context length in {name} and start again.",
            )

    if args.prepare and isinstance(copilot, PreparedCopilot):
        bridge.status.emit(
            f"Preparing answers to {args.prepare} expected questions…"
        )
        copilot.prepare(
            copilot.expected_questions(args.prepare)
        )

    holder["copilot"] = copilot
    copilot_ready.set()

    bridge.status.emit("Loading speech model…")

    before, pending, last_final, card = "", "", 0.0, 0

    listener = StreamingTranscriber(
        "system",
        vocabulary=args.vocabulary,
    )

    for event in listener.events(
        on_ready=lambda: bridge.status.emit(
            "Listening · nothing saved"
        ),
        on_restart=lambda why: bridge.status.emit(
            f"Reconnecting audio… ({why})"
        ),
    ):
        joined = (
            f"{pending} {event.text}".strip()
            if event.started - last_final < JOIN_SECONDS
            else event.text
        )

        bridge.heard.emit(joined)

        if event.kind == "final":
            if joined != event.text and card:
                line = joined
            else:
                line, before, card = (
                    event.text,
                    pending or before,
                    new_card(),
                )

            pending, last_final = line, event.at

            threading.Thread(
                target=run_answer,
                args=(copilot, bridge, card, line, before, event.at),
                daemon=True,
            ).start()


def restore_window_position(
    window: QWidget,
    app: QApplication,
    settings,
) -> bool:
    """Restore the saved position if the window intersects an available screen."""
    saved_position = settings.value("window/position")

    if saved_position is None:
        return False

    if not isinstance(saved_position, QPoint):
        try:
            saved_position = QPoint(
                int(saved_position[0]),
                int(saved_position[1]),
            )
        except (TypeError, ValueError, IndexError):
            return False

    window_geometry = QRect(
        saved_position,
        window.size(),
    )

    visible = any(
        window_geometry.intersects(screen.availableGeometry())
        for screen in app.screens()
    )

    if not visible:
        return False

    window.move(saved_position)
    return True


def save_window_position(window: QWidget, settings) -> None:
    """Save the floating window position for the next launch."""
    settings.setValue("window/position", window.pos())
    settings.sync()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Live answers from your documents during a call"
    )

    parser.add_argument(
        "--docs",
        nargs="*",
        default=[],
        help="PDF, Excel or text files",
    )
    parser.add_argument(
        "--situation",
        default="a meeting where the user is asked questions",
        help='what the call is, e.g. "a seed pitch to an investor"',
    )
    parser.add_argument(
        "--vocabulary",
        default="",
        help="names the transcription should get right, comma separated",
    )
    parser.add_argument(
        "--prepare",
        type=int,
        default=0,
        help="prepare answers to N expected questions first",
    )
    parser.add_argument(
        "--provider",
        choices=[p.id for p in providers.PROVIDERS],
        default=None,
        help="the AI service whose API key answers (default: as on the setup screen)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="answer model (default: as on the setup screen)",
    )
    parser.add_argument(
        "--show-in-screenshots",
        action="store_true",
        help="testing only: let screenshots and screen sharing see the window",
    )

    args = parser.parse_args(argv)

    import os
    import subprocess

    subprocess.Popen(
        ["caffeinate", "-di", "-w", str(os.getpid())]
    )

    app = QApplication(sys.argv)
    app.setFont(QFont(".AppleSystemUIFont", 13))
    theme.apply_saved()

    if not args.docs:
        from .setup import SetupDialog

        dialog = SetupDialog()

        if dialog.exec() != SetupDialog.DialogCode.Accepted:
            return

        config = dialog.config()

        args.docs = config.docs
        args.situation = config.situation
        args.vocabulary = config.vocabulary
        args.prepare = config.prepare
        args.model = config.model
        args.style = config.style
        args.provider = config.provider

    else:
        from .setup import default_provider, load_style

        args.style = load_style()
        args.provider = args.provider or default_provider()

        args.model = (
            args.model
            or settings_store().value(f"model_{args.provider}")
            or "claude-sonnet-5-5"
        )


    global MAX_LINES, FORMAT

    MAX_LINES = args.style.lines
    FORMAT = args.style.format

    bridge = Bridge()
    ready = threading.Event()
    holder: dict = {}

    def ask(text: str) -> None:
        if ready.is_set():
            threading.Thread(
                target=run_answer,
                args=(
                    holder["copilot"],
                    bridge,
                    new_card(),
                    text,
                    "",
                    time.perf_counter(),
                ),
                daemon=True,
            ).start()

    # Create the window and load its saved position.
    window = Window(bridge, ask)
    settings = settings_store()

    restored = restore_window_position(
        window,
        app,
        settings,
    )

    # Keep today's default position when nothing is saved
    # or when the saved position belongs to a disconnected monitor.
    if not restored:
        window.move(
            app.primaryScreen().availableGeometry().topRight()
            - QPoint(470, -40)
        )

    window.show()

    if snapshot := os.environ.get("COPILOT_SNAPSHOT"):
        bridge.timing.connect(
            lambda _t: window.grab().save(snapshot)
        )

    hidden = configure_native_window(
        window,
        hide_from_capture=not args.show_in_screenshots,
    )

    if not hidden and not args.show_in_screenshots:
        bridge.status.emit(
            "Warning: this window may be visible when you share your screen"
        )

    threading.Thread(
        target=start,
        args=(ready, holder, bridge, args),
        daemon=True,
    ).start()

    app.aboutToQuit.connect(count_answered_call)

    # Persist the last window position whenever the application quits.
    app.aboutToQuit.connect(
        lambda: save_window_position(window, settings)
    )

    app.exec()


def count_answered_call() -> None:
    """Count one more call in which Murmury answered something."""
    if ANSWERED.is_set():

        settings = settings_store()

        settings.setValue(
            "answered_calls",
            int(settings.value("answered_calls", 0) or 0) + 1,
        )


if __name__ == "__main__":
    main()
