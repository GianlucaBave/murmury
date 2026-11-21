import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from copilot.setup import default_provider, settings_store


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """Every test writes to the test preferences, never to the real Murmury ones."""
    monkeypatch.setenv("MURMURY_TEST_SETTINGS", "1")
    store = settings_store()
    assert store.organizationName() == "Murmury-test"  # safety net
    store.remove("provider")
    store.sync()
    yield store
    store.remove("provider")
    store.sync()


def test_nothing_saved_gives_anthropic():
    assert default_provider() == "anthropic"


def test_saved_provider_is_preselected():
    settings_store().setValue("provider", "openai")
    assert default_provider() == "openai"


def test_saved_id_that_no_longer_exists_gives_anthropic():
    settings_store().setValue("provider", "not-a-service")
    assert default_provider() == "anthropic"
