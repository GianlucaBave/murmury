import openai
import pytest

from copilot import providers
from copilot.answer import Answer
from copilot.openai_copilot import OpenAICopilot, _reasoning
from copilot.pipeline import respond


@pytest.mark.parametrize("provider_id, model, expected", [
    ("ollama", "qwen3:8b", {"reasoning_effort": "none"}),
    ("openai", "gpt-5.1-mini", {"reasoning_effort": "none"}),
    ("openai", "gpt-5", {"reasoning_effort": "minimal"}),
    ("openrouter", "openai/gpt-5.2", {"reasoning_effort": "none"}),
    ("gemini", "gemini-2.5-flash", {"reasoning_effort": "none"}),
    ("gemini", "gemini-2.5-pro", {"reasoning_effort": "low"}),
    ("groq", "openai/gpt-oss-120b", {"reasoning_effort": "low"}),
    ("lm-studio", "qwen3-8b", {}),
    ("mistral", "mistral-small-latest", {}),
])
def test_reasoning_asks_for_as_little_thinking_as_the_model_allows(provider_id, model, expected):
    assert _reasoning(provider_id, model) == expected


def test_local_servers_get_time_to_read_long_documents():
    local = OpenAICopilot("", "", providers.provider("ollama"), "local", "gemma3:12b")
    cloud = OpenAICopilot("", "", providers.provider("openai"), "sk-test", "gpt-5.1-mini")
    assert local.client.timeout == 600
    assert cloud.client.timeout == 60


def test_a_refused_field_is_dropped_and_the_call_repeated():
    copilot = OpenAICopilot("", "", providers.provider("ollama"), "local", "gemma3:12b")
    sent = []

    def create(**fields):
        sent.append(fields)
        if "reasoning_effort" in fields:
            error = openai.BadRequestError.__new__(openai.BadRequestError)  # no HTTP response needed here
            Exception.__init__(error, "unknown field: reasoning_effort")
            raise error
        return iter(())

    copilot.client.chat.completions.create = create
    copilot._call("Last line heard: hello", 16)
    assert "reasoning_effort" in sent[0] and "reasoning_effort" not in sent[1]
    assert "reasoning_effort" not in copilot.optional  # not sent again on the next line


class Gated:
    """A copilot whose answer says SKIP when the line is not a question, like OpenAICopilot."""
    gatekeeps = True

    def __init__(self, *parts):
        self.parts = parts

    def answer(self, line, before=""):
        yield from self.parts
        yield Answer(line, "".join(self.parts), 0.1, 0.2)


def test_a_skip_answer_is_dropped():
    shown = list(respond(Gated("SK", "IP"), "Thanks everyone, let's get started."))
    assert [s.kind for s in shown] == ["dropped"]


def test_a_real_answer_streams_then_completes():
    shown = list(respond(Gated("SAY: ", "Runway is ", "15 months."), "How long is your runway?"))
    assert shown[-1].kind == "live-done" and shown[-1].text == "SAY: Runway is 15 months."
    assert "".join(s.text for s in shown if s.kind == "live-chunk") == "SAY: Runway is 15 months."
def test_custom_system_prompt_preserves_original():
    copilot = OpenAICopilot(
        "Original documents", "", providers.provider("ollama"),
        "local", "gemma3:12b"
    )
    original = copilot.system
    sent = []

    def create(**fields):
        sent.append(fields)
        return iter(())

    copilot.client.chat.completions.create = create

    copilot._call("Question", 16, system="Retrieved documents")
    copilot._call("Question", 16)

    assert sent[0]["messages"][0]["content"] == "Retrieved documents"
    assert sent[1]["messages"][0]["content"] == original
    assert copilot.system == original


def test_retrieval_is_disabled_by_default():
    copilot = OpenAICopilot(
        "Documents", "", providers.provider("ollama"),
        "local", "gemma3:12b"
    )

    assert copilot.retrieval_index is None
    assert copilot.retrieval_backend is None
    assert copilot.context_limit is None


def test_hosted_provider_cannot_enable_retrieval():
    copilot = OpenAICopilot(
        "Documents", "", providers.provider("openai"),
        "sk-test", "gpt-5.1-mini"
    )

    copilot.enable_retrieval([], 4096)

    assert copilot.retrieval_index is None
    assert copilot.retrieval_backend is None
    assert copilot.context_limit is None
def test_active_retrieval_uses_selected_documents(monkeypatch):
    from unittest.mock import MagicMock
    from copilot import fastembed_backend
    from copilot.material import Source

    copilot = OpenAICopilot(
        "Full original documents", "",
        providers.provider("ollama"),
        "local", "gemma3:12b"
    )

    backend = MagicMock()
    backend.count_tokens.side_effect = lambda text: len(text.split())

    index = MagicMock()
    index.retrieve_prompt.return_value = "Relevant document chunk"
    backend.build_index.return_value = index

    factory = MagicMock(return_value=backend)
    monkeypatch.setattr(fastembed_backend, "FastEmbedBackend", factory)

    sources = [Source("report.txt", "text", "Full original documents")]
    original = copilot.system

    copilot.enable_retrieval(sources, 4096)

    sent = []

    def create(**fields):
        sent.append(fields)
        return MagicMock(__iter__=lambda self: iter(()))

    copilot.client.chat.completions.create = create

    list(copilot.answer("What is the revenue?"))

    factory.assert_called_once()
    backend.build_index.assert_called_once_with(sources)
    index.retrieve_prompt.assert_called_once()

    assert index.retrieve_prompt.call_args.args[0] == "What is the revenue?"
    assert index.retrieve_prompt.call_args.args[2] > 0
    assert sent[0]["messages"][0]["content"] == (
        copilot.system_prefix + "Relevant document chunk"
    )
    assert copilot.system == original
def test_failed_retrieval_initialization_preserves_original(monkeypatch):
    from unittest.mock import MagicMock
    from copilot import fastembed_backend

    copilot = OpenAICopilot(
        "Full original documents", "",
        providers.provider("ollama"),
        "local", "gemma3:12b"
    )

    original = copilot.system

    factory = MagicMock(
        side_effect=RuntimeError("Embedding model unavailable")
    )

    monkeypatch.setattr(
        fastembed_backend, "FastEmbedBackend", factory
    )

    with pytest.raises(RuntimeError, match="Embedding model unavailable"):
        copilot.enable_retrieval([], 4096)

    assert copilot.retrieval_index is None
    assert copilot.retrieval_backend is None
    assert copilot.context_limit is None
    assert copilot.system == original