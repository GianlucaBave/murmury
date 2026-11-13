import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from copilot.setup import Slider, TextBox, settings_store


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """Ensure tests run against isolated test preferences, never user preferences."""
    monkeypatch.setenv("MURMURY_TEST_SETTINGS", "1")
    store = settings_store()
    assert store.organizationName() == "Murmury-test"
    yield store


@pytest.fixture
def make_textbox(application):
    widgets = []

    def _make(placeholder: str = "Notes", limit: int = 20, lines: int = 3) -> TextBox:
        box = TextBox(placeholder=placeholder, limit=limit, lines=lines)
        widgets.append(box)
        return box

    yield _make
    for widget in widgets:
        widget.close()
        widget.deleteLater()
    application.processEvents()


@pytest.fixture
def box(make_textbox):
    return make_textbox(placeholder="Notes", limit=20)


@pytest.fixture
def make_slider(application):
    widgets = []

    def _make(
        low: int = 1, high: int = 30, one: str = "word", many: str = "words"
    ) -> Slider:
        widget = Slider(low=low, high=high, one=one, many=many)
        widgets.append(widget)
        return widget

    yield _make
    for widget in widgets:
        widget.close()
        widget.deleteLater()
    application.processEvents()


@pytest.fixture
def slider(make_slider):
    return make_slider(low=1, high=30, one="word", many="words")


# ---------- TextBox tests ----------


@pytest.mark.parametrize("limit", [10, 50, 140])
def test_initial_counter_displays_zero_and_configured_limit(make_textbox, limit):
    box = make_textbox(limit=limit)
    assert box.counter.text() == f"0/{box.limit}"
    assert box.counter.text() == f"0/{limit}"
    assert box.text() == ""


@pytest.mark.parametrize(
    "content", ["", "a", "hello", "ten letters", "exact limit 20 chars"]
)
def test_counter_updates_with_text_length(box, content):
    box.edit.setPlainText(content)
    assert box.counter.text() == f"{len(content)}/{box.limit}"
    assert box.text() == content


def test_counter_updates_when_text_is_cleared(box):
    box.edit.setPlainText("initial text")
    assert box.counter.text() == f"12/{box.limit}"
    box.edit.setPlainText("")
    assert box.counter.text() == f"0/{box.limit}"
    assert box.text() == ""


def test_typing_beyond_character_limit_is_truncated(make_textbox):
    box = make_textbox(limit=10)
    QTest.keyClicks(box.edit, "1234567890EXTRA")
    assert len(box.text()) == box.limit
    assert box.text() == "1234567890"
    assert "EXTRA" not in box.text()
    assert box.counter.text() == f"{box.limit}/{box.limit}"


def test_pasting_beyond_character_limit_removes_extra_characters(make_textbox):
    box = make_textbox(limit=10)
    long_text = "pasting past the allowed limit"
    box.edit.insertPlainText(long_text)
    assert box.text() == long_text[:10]
    assert len(box.text()) == box.limit
    assert box.counter.text() == f"{box.limit}/{box.limit}"


def test_cursor_remains_at_limit_when_pasting_at_end_past_limit(make_textbox):
    box = make_textbox(limit=10)
    box.edit.insertPlainText("1234567890EXTRA")
    assert box.edit.textCursor().position() == box.limit
    assert box.text() == "1234567890"


def test_cursor_position_preserved_when_inserting_in_middle(make_textbox):
    box = make_textbox(limit=10)
    box.setText("123456789")  # 9 characters
    cursor = box.edit.textCursor()
    cursor.setPosition(3)
    box.edit.setTextCursor(cursor)
    # Insert 4 characters at position 3: total 13 chars > 10 limit
    # Cursor was at 3, moves to 3 + 4 = 7 <= 10 limit
    box.edit.insertPlainText("ABCD")
    assert box.edit.textCursor().position() == 7
    assert box.text() == "123ABCD456"
    assert len(box.text()) == 10


def test_set_text_with_oversized_string_retains_only_limit_characters(make_textbox):
    box = make_textbox(limit=12)
    oversized_text = "This string is definitely longer than 12 characters"
    box.setText(oversized_text)
    assert box.text() == oversized_text[:12]
    assert len(box.text()) == box.limit
    assert box.counter.text() == f"{box.limit}/{box.limit}"


def test_changed_signal_emitted_on_text_change(box):
    spy = QSignalSpy(box.changed)
    assert spy.isValid()
    assert spy.count() == 0

    box.edit.setPlainText("new text")
    assert spy.count() >= 1
    assert spy.at(0) == []

    current_count = spy.count()
    box.setText("updated text")
    assert spy.count() > current_count
    assert spy.at(current_count) == []


# ---------- Slider tests ----------


def test_slider_singular_label(slider):
    slider.setValue(1)
    assert slider.label.text() == "1 word"
    assert slider.value() == 1


def test_slider_plural_label(slider):
    slider.setValue(12)
    assert slider.label.text() == "12 words"
    assert slider.value() == 12


def test_slider_custom_singular_and_plural_units(make_slider):
    custom_slider = make_slider(low=1, high=10, one="second", many="seconds")
    custom_slider.setValue(1)
    assert custom_slider.label.text() == "1 second"
    custom_slider.setValue(5)
    assert custom_slider.label.text() == "5 seconds"


def test_slider_value_changed_signal_emits_new_value(slider):
    spy = QSignalSpy(slider.valueChanged)
    assert spy.isValid()
    assert spy.count() == 0

    slider.setValue(12)
    assert spy.count() == 1
    assert spy.at(0) == [12]

    slider.setValue(5)
    assert spy.count() == 2
    assert spy.at(1) == [5]
