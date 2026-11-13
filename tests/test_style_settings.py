import pytest

from copilot.answer import PRESETS, Style
from copilot.setup import load_style, save_style, settings_store


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("MURMURY_TEST_SETTINGS", "1")
    store = settings_store()
    store.clear()
    store.sync()
    yield store
    store.clear()
    store.sync()


@pytest.mark.parametrize("preset", PRESETS.values())
def test_every_preset_can_be_saved_and_loaded(settings, preset):
    save_style(settings, preset)
    assert load_style(settings) == preset


def test_custom_style_can_be_saved_and_loaded(settings):
    custom = Style(
        tone="cautious",
        language="English",
        extra="Include practical examples",
        format="script",
        sources=False,
    )
    save_style(settings, custom)
    assert load_style(settings) == custom


def test_empty_settings_return_default_style(settings):
    assert load_style(settings) == Style()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("false", False),
        (True, True),
        (False, False),
    ],
)
def test_sources_is_always_a_boolean(settings, raw, expected):
    settings.setValue("style/sources", raw)
    result = load_style(settings)
    assert result.sources is expected
    assert isinstance(result.sources, bool)


def test_invalid_say_words_uses_default_and_loads_other_fields(settings):
    settings.setValue("style/say_words", "abc")
    settings.setValue("style/lines", "5")
    settings.setValue("style/tone", "cautious")

    result = load_style(settings)

    assert result.say_words == 12
    assert result.lines == 5
    assert result.tone == "cautious"
