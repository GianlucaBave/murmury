import httpx
import openai
import pytest

from copilot.openai_copilot import is_context_overflow


def bad_request(message, code=None):
    return openai.BadRequestError(
        message,
        response=httpx.Response(
            400,
            request=httpx.Request(
                "POST",
                "http://localhost/v1/chat/completions",
            ),
        ),
        body={"code": code},
    )


@pytest.mark.parametrize(
    "message",
    [
        "Maximum context length is 4096 tokens",
        "Context length exceeded",
        "Context window exceeded",
        "Input exceeds the context length",
        "Prompt exceeds the context window",
        "Input length exceeds the limit",
        "Prompt is too long",
    ],
)
def test_context_overflow_messages(message):
    assert is_context_overflow(bad_request(message))


def test_context_overflow_error_code():
    error = bad_request(
        "Invalid request",
        code="context_length_exceeded",
    )

    assert is_context_overflow(error)


@pytest.mark.parametrize(
    "message",
    [
        "Invalid API key",
        "Model not found",
        "Unsupported parameter",
        "Invalid temperature",
    ],
)
def test_unrelated_bad_request(message):
    assert not is_context_overflow(bad_request(message))


def test_connection_error():
    assert not is_context_overflow(
        ConnectionError("Server unavailable")
    )


def test_unrelated_exception():
    assert not is_context_overflow(
        RuntimeError("Unexpected error")
    )