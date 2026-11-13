import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MURMURY_TEST_SETTINGS", "1")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from copilot.setup import Slider, TextBox

_app = QApplication.instance() or QApplication([])


def test_textbox_counter_tracks_text_changes():
    box = TextBox("Situation", limit=12)

    assert box.counter.text() == "0/12"

    box.edit.setPlainText("hello")
    assert box.counter.text() == "5/12"

    box.edit.clear()
    assert box.counter.text() == "0/12"


def test_textbox_typing_past_limit_truncates_at_limit():
    box = TextBox("Vocabulary", limit=5)
    box.edit.setPlainText("abc")
    cursor = box.edit.textCursor()
    cursor.setPosition(len("abc"))
    box.edit.setTextCursor(cursor)

    QTest.keyClicks(box.edit, "xyz")

    assert box.text() == "abcxy"
    assert box.edit.textCursor().position() == 5
    assert box.counter.text() == "5/5"


def test_textbox_paste_past_limit_preserves_cursor_position():
    box = TextBox("Vocabulary", limit=6)
    box.edit.setPlainText("abcd")
    cursor = box.edit.textCursor()
    cursor.setPosition(2)
    box.edit.setTextCursor(cursor)

    box.edit.insertPlainText("XYZ")

    assert box.text() == "abXYZc"
    assert box.edit.textCursor().position() == 5
    assert box.counter.text() == "6/6"


def test_textbox_set_text_truncates_to_limit():
    box = TextBox("Situation", limit=5)

    box.setText("longer than the limit")

    assert box.text() == "longe"
    assert box.counter.text() == "5/5"


def test_textbox_changed_signal_is_emitted_when_text_changes():
    box = TextBox("Situation", limit=12)
    changes = []
    box.changed.connect(lambda: changes.append(box.text()))

    box.edit.setPlainText("hello")

    assert changes == ["hello"]


def test_slider_label_uses_singular_and_plural():
    slider = Slider(1, 12, "word", "words")

    assert slider.label.text() == "1 word"

    slider.setValue(12)
    assert slider.label.text() == "12 words"


def test_slider_value_changed_emits_new_value():
    slider = Slider(1, 12, "word", "words")
    values = []
    slider.valueChanged.connect(values.append)

    slider.setValue(7)

    assert values == [7]
