import pytest

from copilot.setup import Config
from copilot import providers


def test_retrieval_disabled_by_default():
    assert Config().retrieval is False


def test_retrieval_explicitly_enabled():
    config = Config(retrieval=True)
    assert config.retrieval is True


@pytest.mark.parametrize("provider_id", ["ollama", "lm-studio"])
def test_local_provider_retrieval_config(provider_id):
    config = Config(provider=provider_id, retrieval=True)
    assert config.retrieval is True
    assert providers.provider(config.provider).key_required is False


@pytest.mark.parametrize("provider_id", ["ollama", "lm-studio"])
def test_local_provider_retrieval_defaults_off(provider_id):
    config = Config(provider=provider_id)
    assert config.retrieval is False