import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

from copilot.setup import SetupDialog, settings_store


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
def dialog(application):
    d = SetupDialog()
    d.pages.setCurrentIndex(1)
    d.show()
    yield d
    d.close()
    d.deleteLater()
    application.processEvents()


def test_mix_of_supported_and_unsupported_files(dialog, tmp_path):
    valid1 = tmp_path / "spec.pdf"
    valid1.write_text("PDF content")
    valid2 = tmp_path / "notes.md"
    valid2.write_text("Notes content")
    unsupported = tmp_path / "brief.doc"
    unsupported.write_text("Doc content")

    dialog.add_paths([str(valid1), str(unsupported), str(valid2)])

    assert dialog.paths() == [str(valid1), str(valid2)]
    assert dialog.drop_warning.isVisible() is True
    text = dialog.drop_warning.text()
    assert "Left out: brief.doc (not a supported type)" in text


def test_folder_and_nonexistent_file_are_named_with_reasons(dialog, tmp_path):
    folder = tmp_path / "documents"
    folder.mkdir()
    missing = tmp_path / "missing.pdf"

    dialog.add_paths([str(folder), str(missing)])

    assert dialog.paths() == []
    assert dialog.drop_warning.isVisible() is True
    text = dialog.drop_warning.text()
    assert "documents (folder)" in text
    assert "missing.pdf (does not exist)" in text


def test_adding_only_supported_files_shows_no_message(dialog, tmp_path):
    deck = tmp_path / "deck.pptx"
    deck.write_text("PPTX content")
    sheet = tmp_path / "sheet.xlsx"
    sheet.write_text("XLSX content")

    dialog.add_paths([str(deck), str(sheet)])

    assert dialog.paths() == [str(deck), str(sheet)]
    assert dialog.drop_warning.text() == ""
    assert dialog.drop_warning.isVisible() is False


def test_warning_message_clears_when_subsequent_valid_files_added(dialog, tmp_path):
    unsupported = tmp_path / "archive.zip"
    unsupported.write_text("zip")
    dialog.add_paths([str(unsupported)])
    assert dialog.drop_warning.isVisible() is True
    assert "archive.zip" in dialog.drop_warning.text()

    valid = tmp_path / "contract.docx"
    valid.write_text("Docx")
    dialog.add_paths([str(valid)])

    assert str(valid) in dialog.paths()
    assert dialog.drop_warning.text() == ""
    assert dialog.drop_warning.isVisible() is False


def test_warning_message_clears_when_removed(dialog, tmp_path):
    valid = tmp_path / "valid.txt"
    valid.write_text("text")
    unsupported = tmp_path / "image.png"
    unsupported.write_text("png")
    dialog.add_paths([str(valid), str(unsupported)])
    assert dialog.drop_warning.isVisible() is True

    dialog.remove_path(str(valid))
    assert dialog.drop_warning.text() == ""
    assert dialog.drop_warning.isVisible() is False


def test_warning_message_clears_on_call_switch(dialog, tmp_path):
    unsupported = tmp_path / "script.sh"
    unsupported.write_text("echo")
    dialog.add_paths([str(unsupported)])
    assert dialog.drop_warning.isVisible() is True

    dialog.back_to_calls()
    assert dialog.drop_warning.text() == ""
    assert dialog.drop_warning.isVisible() is False
