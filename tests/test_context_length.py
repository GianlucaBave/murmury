import io
import json
from unittest.mock import patch

import pytest

from copilot import providers


def response(data):
    return io.BytesIO(json.dumps(data).encode("utf-8"))


def test_ollama_context_length():
    data = {
        "models": [
            {
                "name": "gemma3:12b",
                "context_length": 8192,
            }
        ]
    }

    with patch(
        "urllib.request.urlopen",
        return_value=response(data),
    ) as request:
        result = providers.local_context_length(
            providers.provider("ollama"),
            "gemma3:12b",
        )

    assert result == 8192
    request.assert_called_once_with(
        "http://localhost:11434/api/ps",
        timeout=3,
    )


def test_lm_studio_context_length():
    data = {
        "models": [
            {
                "key": "qwen3",
                "loaded_instances": [
                    {
                        "id": "qwen3",
                        "config": {
                            "context_length": 16384
                        },
                    }
                ],
            }
        ]
    }

    with patch(
        "urllib.request.urlopen",
        return_value=response(data),
    ) as request:
        result = providers.local_context_length(
            providers.provider("lm-studio"),
            "qwen3",
        )

    assert result == 16384
    request.assert_called_once_with(
        "http://localhost:1234/api/v1/models",
        timeout=3,
    )


def test_custom_server_address():
    service = providers.with_address(
        providers.provider("ollama"),
        "http://192.168.1.10:11434",
    )

    with patch(
        "urllib.request.urlopen",
        return_value=response({"models": []}),
    ) as request:
        providers.local_context_length(service, "gemma3")

    request.assert_called_once_with(
        "http://192.168.1.10:11434/api/ps",
        timeout=3,
    )


def test_hosted_provider_does_not_make_request():
    with patch("urllib.request.urlopen") as request:
        result = providers.local_context_length(
            providers.provider("openai"),
            "gpt-5",
        )

    assert result is None
    request.assert_not_called()


def test_server_unavailable():
    with patch(
        "urllib.request.urlopen",
        side_effect=OSError("Server unavailable"),
    ):
        result = providers.local_context_length(
            providers.provider("ollama"),
            "gemma3",
        )

    assert result is None


def test_model_not_loaded():
    with patch(
        "urllib.request.urlopen",
        return_value=response({"models": []}),
    ):
        result = providers.local_context_length(
            providers.provider("ollama"),
            "gemma3",
        )

    assert result is None


@pytest.mark.parametrize(
    "length",
    [None, 0, -1, "4096", True],
)
def test_invalid_context_length(length):
    data = {
        "models": [
            {
                "name": "gemma3",
                "context_length": length,
            }
        ]
    }

    with patch(
        "urllib.request.urlopen",
        return_value=response(data),
    ):
        result = providers.local_context_length(
            providers.provider("ollama"),
            "gemma3",
        )

    assert result is None

def test_estimate_prompt_tokens():
    assert providers.estimate_prompt_tokens("abc" * 100) == 100


def test_empty_prompt():
    assert providers.estimate_prompt_tokens("") == 0


def test_prompt_fits_context():
    assert not providers.context_overflows(
        "abc" * 1000,
        4096,
    )


def test_prompt_exceeds_context():
    assert providers.context_overflows(
        "abc" * 5000,
        4096,
    )


def test_reserved_tokens_are_considered():
    assert providers.context_overflows(
        "abc" * 3800,
        4096,
        reserved_tokens=512,
    )


def test_exact_context_boundary():
    assert not providers.context_overflows(
        "abc" * 3584,
        4096,
        reserved_tokens=512,
    )