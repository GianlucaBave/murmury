import pytest

from copilot import providers


def test_local_providers_use_openai_compatible_endpoints_without_keys():
    expected = {
        "ollama": "http://localhost:11434/v1",
        "lm-studio": "http://localhost:1234/v1",
    }

    for provider_id, base_url in expected.items():
        service = providers.provider(provider_id)
        assert service.base_url == base_url
        assert service.key_required is False
        assert providers.api_key(provider_id) == (None, "")


def test_local_provider_model_listing_uses_placeholder_key(monkeypatch):
    calls = {}

    class Models:
        def list(self):
            return [type("Model", (), {"id": "llama3.2"})()]

    class Client:
        def __init__(self, **kwargs):
            calls.update(kwargs)
            self.models = Models()

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: Client(**kwargs))

    assert providers.list_models("ollama") == ["llama3.2"]
    assert calls["api_key"] == "local"
    assert calls["base_url"] == "http://localhost:11434/v1"


def test_local_provider_suggestions_do_not_fetch_remote_recommendations(monkeypatch):
    def unexpected_network_call():
        raise AssertionError("local provider suggestions must work offline")

    monkeypatch.setattr(providers, "recommended", unexpected_network_call)
    assert providers.suggest("ollama", ["llama3.2"]) == "llama3.2"


OLLAMA = "http://localhost:11434/v1"


def test_address_empty_keeps_localhost_default():
    assert providers.normalize_address("", OLLAMA) == OLLAMA
    assert providers.normalize_address("   ", OLLAMA) == OLLAMA
    assert providers.normalize_address(None, OLLAMA) == OLLAMA
    assert providers.with_address(providers.provider("ollama"), "").base_url == OLLAMA
    assert (
        providers.with_address(providers.provider("lm-studio"), None).base_url
        == "http://localhost:1234/v1"
    )


@pytest.mark.parametrize(
    "typed",
    [
        "http://mac-mini.local:11434",
        "http://mac-mini.local:11434/",
        "http://mac-mini.local:11434/v1",
        "http://mac-mini.local:11434/v1/",
        "  http://mac-mini.local:11434  ",
        "HTTP://mac-mini.local:11434",
    ],
)
def test_valid_addresses_all_give_the_same_base_url(typed):
    assert (
        providers.normalize_address(typed, OLLAMA) == "http://mac-mini.local:11434/v1"
    )


def test_addresses_with_other_hosts_ports_and_https():
    assert (
        providers.normalize_address("http://192.168.1.20:11434", OLLAMA)
        == "http://192.168.1.20:11434/v1"
    )
    assert (
        providers.normalize_address("https://gpu-box.example.com", OLLAMA)
        == "https://gpu-box.example.com/v1"
    )
    assert (
        providers.normalize_address("https://gpu-box.example.com/ollama/", OLLAMA)
        == "https://gpu-box.example.com/ollama/v1"
    )


@pytest.mark.parametrize(
    "typed",
    [
        "mac-mini.local:11434",  # no scheme
        "ftp://mac-mini.local",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "http://",
        "http://mac mini.local:11434",
        "http://mac-mini.local:abc",
    ],
)
def test_invalid_addresses_are_refused(typed):
    with pytest.raises(ValueError, match="http://"):
        providers.normalize_address(typed, OLLAMA)


def test_only_local_providers_take_an_address():
    openai = providers.provider("openai")
    assert providers.with_address(openai, "http://mac-mini.local:11434") is openai
    anthropic = providers.provider("anthropic")
    assert providers.with_address(anthropic, "http://mac-mini.local:11434") is anthropic
    ollama = providers.with_address(
        providers.provider("ollama"), "http://mac-mini.local:11434"
    )
    assert ollama.base_url == "http://mac-mini.local:11434/v1"
    assert (
        providers.provider("ollama").base_url == OLLAMA
    )  # the shared definition is not changed


def test_model_list_comes_from_the_given_address(monkeypatch):
    calls = {}

    class Models:
        def list(self):
            return [type("Model", (), {"id": "gemma3:12b"})()]

    class Client:
        def __init__(self, **kwargs):
            calls.update(kwargs)
            self.models = Models()

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: Client(**kwargs))

    assert providers.list_models("ollama", address="http://mac-mini.local:11434") == [
        "gemma3:12b"
    ]
    assert calls["base_url"] == "http://mac-mini.local:11434/v1"
    assert calls["api_key"] == "local"
    with pytest.raises(ValueError):
        providers.list_models("ollama", address="ftp://mac-mini.local")


def test_answers_use_the_given_address():
    from copilot.openai_copilot import OpenAICopilot

    service = providers.with_address(
        providers.provider("ollama"), "http://mac-mini.local:11434"
    )
    copilot = OpenAICopilot("doc", "a call", service, "local", "gemma3:12b")
    assert str(copilot.client.base_url).rstrip("/") == "http://mac-mini.local:11434/v1"

