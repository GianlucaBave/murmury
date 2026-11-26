import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest

from copilot import app
from copilot.answer import Usage
from copilot.material import Source


@pytest.fixture
def startup():
    args = SimpleNamespace(
        docs=["report.txt"],
        provider="ollama",
        address=None,
        situation="",
        model="gemma3",
        style=None,
        retrieval=True,
        prepare=0,
        vocabulary=[],
    )

    bridge = MagicMock()
    copilot = MagicMock()
    copilot.system = "abc " * 6000
    copilot.system_prefix = "Instructions"
    copilot.warm.return_value = Usage(2000, 0, 0, 16)

    sources = [
        Source("report.txt", "text", "Document content")
    ]

    with (
        patch.object(app.material, "load", return_value=sources),
        patch.object(app, "OpenAICopilot", return_value=copilot),
        patch.object(app, "StreamingTranscriber") as listener,
        patch.object(
            app.providers,
            "local_context_length",
            return_value=4096,
        ) as context,
    ):
        listener.return_value.events.return_value = []

        yield SimpleNamespace(
            args=args,
            bridge=bridge,
            copilot=copilot,
            sources=sources,
            context=context,
            ready=threading.Event(),
            holder={},
        )


def run_startup(s):
    app.start(s.ready, s.holder, s.bridge, s.args)


def overflow_error():
    return openai.BadRequestError(
        "Maximum context length exceeded",
        response=httpx.Response(
            400,
            request=httpx.Request(
                "POST", "http://localhost/v1/chat/completions"
            ),
        ),
        body={"code": "context_length_exceeded"},
    )


def test_documents_fit(startup):
    startup.copilot.system = "Short document"

    run_startup(startup)

    startup.copilot.enable_retrieval.assert_not_called()
    startup.context.assert_not_called()
    assert startup.ready.is_set()


def test_silent_truncation(startup):
    run_startup(startup)

    startup.copilot.enable_retrieval.assert_called_once_with(
        startup.sources, 4096
    )
    assert startup.ready.is_set()


def test_retrieval_disabled(startup):
    startup.args.retrieval = False

    run_startup(startup)

    startup.copilot.enable_retrieval.assert_not_called()
    startup.context.assert_not_called()
    assert startup.ready.is_set()


def test_context_metadata_unavailable(startup):
    startup.context.return_value = None

    run_startup(startup)

    startup.copilot.enable_retrieval.assert_called_once_with(
        startup.sources, 2000
    )


def test_embedding_initialization_failure(startup):
    startup.copilot.enable_retrieval.side_effect = RuntimeError(
        "Embedding unavailable"
    )

    run_startup(startup)

    startup.bridge.warning.emit.assert_called()
    assert startup.ready.is_set()


def test_explicit_overflow_recovery(startup):
    startup.copilot.warm.side_effect = [
        overflow_error(),
        Usage(100, 0, 0, 16),
    ]

    run_startup(startup)

    assert startup.copilot.warm.call_count == 2
    startup.copilot.warm.assert_called_with(
        system=startup.copilot.system_prefix
    )
    startup.copilot.enable_retrieval.assert_called_once_with(
        startup.sources, 4096
    )
    assert startup.ready.is_set()


def test_explicit_overflow_disabled(startup):
    startup.args.retrieval = False
    startup.copilot.warm.side_effect = overflow_error()

    run_startup(startup)

    startup.copilot.enable_retrieval.assert_not_called()
    assert not startup.ready.is_set()


def test_explicit_overflow_without_context_metadata(startup):
    startup.context.return_value = None
    startup.copilot.warm.side_effect = [
        overflow_error(),
        Usage(100, 0, 0, 16),
    ]

    run_startup(startup)

    startup.copilot.enable_retrieval.assert_not_called()
    assert not startup.ready.is_set()


def test_unrelated_connection_failure(startup):
    startup.copilot.warm.side_effect = ConnectionError(
        "Server unavailable"
    )

    run_startup(startup)

    startup.copilot.warm.assert_called_once()
    startup.copilot.enable_retrieval.assert_not_called()
    assert not startup.ready.is_set()