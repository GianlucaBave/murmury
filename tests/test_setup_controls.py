import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from copilot.setup import Segmented, Switch, settings_store

OPTIONS = [
    ("Talking points", "talking"),
    ("Key facts", "facts"),
    ("Script", "script"),
]


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
def make_segmented(application):
    widgets = []

    def _make(options: list[tuple[str, str]] = OPTIONS) -> Segmented:
        widget = Segmented(options)
        widgets.append(widget)
        return widget

    yield _make
    for widget in widgets:
        widget.close()
        widget.deleteLater()
    application.processEvents()


@pytest.fixture
def segmented(make_segmented):
    return make_segmented()


@pytest.fixture
def make_switch(application):
    widgets = []

    def _make(checked: bool | None = None) -> Switch:
        widget = Switch() if checked is None else Switch(checked)
        widgets.append(widget)
        return widget

    yield _make
    for widget in widgets:
        widget.close()
        widget.deleteLater()
    application.processEvents()


def checked_values(control: Segmented) -> list[str]:
    return [value for value, button in control.buttons.items() if button.isChecked()]


# ---------- Segmented tests ----------


def test_segmented_value_is_empty_before_any_selection(segmented):
    assert segmented.value() == ""
    assert checked_values(segmented) == []


def test_segmented_click_emits_option_value_and_keeps_one_button_checked(segmented):
    spy = QSignalSpy(segmented.changed)
    assert spy.isValid()

    steps = [
        (lambda btn: btn.click(), "talking"),
        (lambda btn: QTest.mouseClick(btn, Qt.MouseButton.LeftButton), "facts"),
        (lambda btn: btn.click(), "script"),
    ]
    for index, (trigger, value) in enumerate(steps, start=1):
        trigger(segmented.buttons[value])
        assert spy.count() == index
        assert spy.at(index - 1) == [value]
        assert segmented.value() == value
        assert checked_values(segmented) == [value]


def test_segmented_clicking_selected_button_keeps_it_checked(segmented):
    segmented.buttons["talking"].click()
    segmented.buttons["talking"].click()
    assert segmented.value() == "talking"
    assert checked_values(segmented) == ["talking"]


def test_segmented_set_value_selects_option_without_emitting_changed(segmented):
    spy = QSignalSpy(segmented.changed)
    assert spy.isValid()

    for value in ("facts", "script"):
        segmented.set_value(value)
        assert spy.count() == 0
        assert segmented.value() == value
        assert checked_values(segmented) == [value]


@pytest.mark.parametrize("initial", ["facts", None])
@pytest.mark.parametrize("unknown", ["not-an-option", ""])
def test_segmented_set_value_unknown_clears_selection_and_stays_exclusive(
    segmented, initial, unknown
):
    if initial is not None:
        segmented.set_value(initial)
        assert segmented.value() == initial

    spy = QSignalSpy(segmented.changed)
    assert spy.isValid()

    segmented.set_value(unknown)
    assert spy.count() == 0
    assert segmented.value() == ""
    assert checked_values(segmented) == []

    for index, value in enumerate(("talking", "script"), start=1):
        segmented.buttons[value].click()
        assert spy.count() == index
        assert spy.at(index - 1) == [value]
        assert segmented.value() == value
        assert checked_values(segmented) == [value]


# ---------- Switch tests ----------


def test_switch_defaults_to_unchecked(make_switch):
    switch = make_switch()
    assert switch.isCheckable() is True
    assert switch.isChecked() is False


@pytest.mark.parametrize("initial", [False, True])
def test_switch_starts_with_given_checked_state(make_switch, initial):
    switch = make_switch(initial)
    assert switch.isChecked() is initial


@pytest.mark.parametrize("initial", [False, True])
def test_switch_click_toggles_checked_state(make_switch, initial):
    switch = make_switch(initial)
    spy = QSignalSpy(switch.toggled)
    assert spy.isValid()

    switch.click()
    assert switch.isChecked() is (not initial)
    assert spy.count() == 1
    assert spy.at(0) == [not initial]

    QTest.mouseClick(switch, Qt.MouseButton.LeftButton)
    assert switch.isChecked() is initial
    assert spy.count() == 2
    assert spy.at(1) == [initial]


@pytest.mark.parametrize("initial", [None, False, True])
def test_switch_size_is_34_by_20(make_switch, initial):
    switch = make_switch(initial)
    assert switch.size() == QSize(34, 20)
    assert switch.width() == 34
    assert switch.height() == 20
    assert switch.minimumSize() == switch.maximumSize() == QSize(34, 20)
