import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from copilot.app import Bridge, Window
from copilot.setup import settings_store


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """Ensure tests run against isolated test preferences, never user preferences."""
    monkeypatch.setenv("MURMURY_TEST_SETTINGS", "1")
    store = settings_store()
    assert store.organizationName() == "Murmury-test"
    store.remove("transcription_notice_dismissed")
    yield store
    store.remove("transcription_notice_dismissed")


def test_consent_notice_displayed_by_default(application):
    bridge = Bridge()
    window = Window(bridge, lambda _: None)
    window.show()

    assert not window.notice.isHidden()
    assert "Let the others on the call know Murmury is transcribing." in window.notice_text.text()

    window.close()
    window.deleteLater()
    application.processEvents()


def test_consent_notice_close_hides_for_session_only(application, test_settings):
    bridge = Bridge()
    window = Window(bridge, lambda _: None)
    window.show()

    assert not window.notice.isHidden()
    window.notice_close.click()
    assert window.notice.isHidden()

    # Setting is NOT saved permanently
    assert test_settings.value("transcription_notice_dismissed") != "true"

    window.close()
    window.deleteLater()
    application.processEvents()

    # Next call / next window still shows notice
    window2 = Window(bridge, lambda _: None)
    window2.show()
    assert not window2.notice.isHidden()

    window2.close()
    window2.deleteLater()
    application.processEvents()


def test_consent_notice_dont_show_again_persists_dismissal(application, test_settings):
    bridge = Bridge()
    window = Window(bridge, lambda _: None)
    window.show()

    assert not window.notice.isHidden()
    window.notice_dont_show.click()
    assert window.notice.isHidden()

    # Setting IS saved permanently
    assert test_settings.value("transcription_notice_dismissed") == "true"

    window.close()
    window.deleteLater()
    application.processEvents()

    # Next call / next window does NOT show notice
    window2 = Window(bridge, lambda _: None)
    window2.show()
    assert window2.notice.isHidden()

    window2.close()
    window2.deleteLater()
    application.processEvents()


def test_listening_status_reveals_notice_if_not_dismissed(application, test_settings):
    bridge = Bridge()
    window = Window(bridge, lambda _: None)
    window.show()

    # Status update with Listening preserves/shows notice
    bridge.status.emit("Listening · nothing saved")
    assert not window.notice.isHidden()

    # Once closed for session, Listening status does not resurrect it
    window.notice_close.click()
    assert window.notice.isHidden()
    bridge.status.emit("Listening · nothing saved")
    assert window.notice.isHidden()

    window.close()
    window.deleteLater()
    application.processEvents()


def test_toggle_compact_mode_hides_and_restores_notice(application):
    bridge = Bridge()
    window = Window(bridge, lambda _: None)
    window.show()

    assert not window.notice.isHidden()

    # Switch to compact mode
    window.toggle_compact()
    assert window.notice.isHidden()

    # Switch back to normal mode
    window.toggle_compact()
    assert not window.notice.isHidden()

    window.close()
    window.deleteLater()
    application.processEvents()
