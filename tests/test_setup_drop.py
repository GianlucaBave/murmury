import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from copilot import theme
from copilot.setup import SetupDialog, settings_store


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """Keep tests isolated from the user's real preferences."""
    monkeypatch.setenv("MURMURY_TEST_SETTINGS", "1")

    store = settings_store()
    store.clear()
    store.setValue("tour_done", "true")
    store.sync()

    yield store

    store.clear()
    store.sync()


@pytest.fixture
def dialog(application, test_settings, monkeypatch):
    # Prevent provider checks from starting background network requests.
    monkeypatch.setattr(SetupDialog, "check_connection", lambda self: None)

    # Prevent test dialogs from being retained by the global theme watcher.
    monkeypatch.setattr(theme, "watch", lambda callback: None)

    widget = SetupDialog()
    yield widget

    widget.close()
    widget.deleteLater()
    application.processEvents()


def test_supported_and_unsupported_files(dialog, tmp_path):
    supported = tmp_path / "report.pdf"
    unsupported = tmp_path / "notes.doc"

    supported.write_text("sample")
    unsupported.write_text("sample")

    dialog.add_paths([str(supported), str(unsupported)])

    assert dialog.paths() == [str(supported)]
    assert "notes.doc (not a supported type)" in dialog.left_out_label.text()
    assert not dialog.left_out_label.isHidden()


def test_folders_and_missing_paths_are_reported(dialog, tmp_path):
    folder = tmp_path / "Documents"
    folder.mkdir()
    missing = tmp_path / "missing.pdf"

    dialog.add_paths([str(folder), str(missing)])

    message = dialog.left_out_label.text()

    assert dialog.paths() == []
    assert "Documents (folder)" in message
    assert "missing.pdf (does not exist)" in message
    assert not dialog.left_out_label.isHidden()


def test_only_supported_files_show_no_warning(dialog, tmp_path):
    pdf = tmp_path / "report.pdf"
    markdown = tmp_path / "notes.md"

    pdf.write_text("sample")
    markdown.write_text("sample")

    dialog.add_paths([str(pdf), str(markdown)])

    assert dialog.paths() == [str(pdf), str(markdown)]
    assert dialog.left_out_label.text() == ""
    assert dialog.left_out_label.isHidden()


def test_previous_warning_disappears_when_next_selection_is_valid(
    dialog, tmp_path
):
    unsupported = tmp_path / "notes.doc"
    supported = tmp_path / "report.txt"

    unsupported.write_text("sample")
    supported.write_text("sample")

    dialog.add_paths([str(unsupported)])
    assert "notes.doc" in dialog.left_out_label.text()

    dialog.add_paths([str(supported)])

    assert dialog.paths() == [str(supported)]
    assert dialog.left_out_label.text() == ""
    assert dialog.left_out_label.isHidden()


def test_new_call_clears_previous_warning(dialog, tmp_path):
    unsupported = tmp_path / "notes.doc"
    unsupported.write_text("sample")

    dialog.add_paths([str(unsupported)])
    assert dialog.left_out_label.text()

    dialog.new_call()

    assert dialog.left_out_label.text() == ""
    assert dialog.left_out_label.isHidden()
