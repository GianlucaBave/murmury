"""Tests for api_key() and save_api_key() in copilot/providers.py."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from copilot import providers


@pytest.fixture(autouse=True)
def _clean_env_and_cache(monkeypatch):
    providers._keychain_cache.clear()
    for p in providers.PROVIDERS:
        for var in p.env:
            monkeypatch.delenv(var, raising=False)
    yield
    providers._keychain_cache.clear()


def _fake_keyring(store: dict[tuple[str, str], str] | None = None, *, error: Exception | None = None):
    data = dict(store or {})
    calls: list[tuple[str, str, str]] = []

    def get_password(service: str, account: str) -> str | None:
        calls.append(("get", service, account))
        if error is not None:
            raise error
        return data.get((service, account))

    def set_password(service: str, account: str, secret: str) -> None:
        calls.append(("set", service, account))
        if error is not None:
            raise error
        data[(service, account)] = secret

    def delete_password(service: str, account: str) -> None:
        calls.append(("delete", service, account))
        if error is not None:
            raise error
        data.pop((service, account), None)

    return SimpleNamespace(
        get_password=get_password,
        set_password=set_password,
        delete_password=delete_password,
        calls=calls,
        data=data,
    )


@pytest.mark.parametrize("provider_id", ["ollama", "lm-studio"])
def test_local_providers_return_none_without_reading_keychain(monkeypatch, provider_id):
    fake = _fake_keyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    assert providers.api_key(provider_id) == (None, "")
    assert fake.calls == []


def test_env_var_wins_over_keychain_and_preserves_order(monkeypatch):
    fake = _fake_keyring({(providers.KEYCHAIN_SERVICE, "anthropic-api-key"): "kc-key"})
    monkeypatch.setitem(sys.modules, "keyring", fake)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-second")
    assert providers.api_key("anthropic") == ("sk-second", "ANTHROPIC_API_KEY")
    assert fake.calls == []

    monkeypatch.setenv("MURMURY_ANTHROPIC_API_KEY", "sk-first")
    assert providers.api_key("anthropic") == ("sk-first", "MURMURY_ANTHROPIC_API_KEY")
    assert fake.calls == []


def test_keychain_value_returned_and_cached_after_first_read(monkeypatch):
    fake = _fake_keyring({(providers.KEYCHAIN_SERVICE, "openai-api-key"): "sk-from-kc"})
    monkeypatch.setitem(sys.modules, "keyring", fake)

    assert providers.api_key("openai") == ("sk-from-kc", "Keychain")
    assert providers.api_key("openai") == ("sk-from-kc", "Keychain")
    assert fake.calls == [("get", providers.KEYCHAIN_SERVICE, "openai-api-key")]


def test_anthropic_falls_back_to_legacy_call_copilot_keychain_entry(monkeypatch):
    fake = _fake_keyring({("call-copilot", "anthropic-api-key"): "sk-legacy"})
    monkeypatch.setitem(sys.modules, "keyring", fake)

    assert providers.api_key("anthropic") == ("sk-legacy", "Keychain")
    assert fake.calls == [
        ("get", providers.KEYCHAIN_SERVICE, "anthropic-api-key"),
        ("get", "call-copilot", "anthropic-api-key"),
    ]


def test_non_anthropic_does_not_check_legacy_keychain_entry(monkeypatch):
    fake = _fake_keyring({("call-copilot", "anthropic-api-key"): "sk-legacy"})
    monkeypatch.setitem(sys.modules, "keyring", fake)

    assert providers.api_key("openai") == (None, "")
    assert fake.calls == [("get", providers.KEYCHAIN_SERVICE, "openai-api-key")]


def test_keychain_error_returns_none_without_crashing(monkeypatch):
    fake = _fake_keyring(error=RuntimeError("keychain locked"))
    monkeypatch.setitem(sys.modules, "keyring", fake)

    assert providers.api_key("openai") == (None, "")
    assert providers.api_key("openai") == (None, "")
    assert len(fake.calls) == 1


def test_save_api_key_stores_and_deletes(monkeypatch):
    fake = _fake_keyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)

    providers.save_api_key("openai", "sk-saved")
    assert fake.data[(providers.KEYCHAIN_SERVICE, "openai-api-key")] == "sk-saved"
    assert providers.api_key("openai") == ("sk-saved", "Keychain")
    assert [c[0] for c in fake.calls] == ["set"]

    providers.save_api_key("openai", "")
    assert (providers.KEYCHAIN_SERVICE, "openai-api-key") not in fake.data
    assert providers.api_key("openai") == (None, "")


def test_save_api_key_empty_ignores_delete_error(monkeypatch):
    fake = _fake_keyring(error=RuntimeError("delete failed"))
    monkeypatch.setitem(sys.modules, "keyring", fake)

    providers.save_api_key("openai", "")
    assert providers.api_key("openai") == (None, "")
