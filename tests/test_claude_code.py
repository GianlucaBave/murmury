"""Tests for the Claude Code stream reader.

Murmury answers through the user's own `claude` login: each line goes to a `claude` process and its
`stream-json` output comes back. None of that was tested, so a change in the event format or a slip in
the parsing would only show up during a real call.

Nothing here starts a process, needs the network, a key or a Mac: the process is a fake object with a
`stdin` to write into and a list of lines to read, and `status()` is checked through monkeypatch.
"""

import io
import json

import pytest

from copilot import claude_code
from copilot.claude_code import ClaudeCodeCopilot


# -- the fake ----------------------------------------------------------------------------------


class FakeProcess:
    """A `claude` process: it writes nothing, and answers with the lines it was given."""

    def __init__(self, lines=()):
        self.stdin = io.StringIO()
        self.stdout = self
        self.lines = list(lines)
        self.read = []

    def __iter__(self):
        for line in self.lines:
            self.read.append(line)
            yield line


def event(**fields) -> str:
    """One line of `stream-json` output."""
    return json.dumps(fields) + "\n"


def text_delta(text: str) -> str:
    """One streamed piece of the answer."""
    return event(type="stream_event", event={"type": "content_block_delta",
                                             "delta": {"type": "text_delta", "text": text}})


def copilot() -> ClaudeCodeCopilot:
    """The copilot without its constructor: it needs `claude` installed, and these tests do not."""
    return object.__new__(ClaudeCodeCopilot)


# -- what goes into the process -----------------------------------------------------------------


def test_the_line_goes_in_as_one_json_line():
    process = FakeProcess()
    list(copilot()._stream(process, "How long is your runway?"))

    written = process.stdin.getvalue()
    assert written.count("\n") == 1
    assert json.loads(written) == {"type": "user",
                                   "message": {"role": "user", "content": "How long is your runway?"}}


# -- what comes out of it -----------------------------------------------------------------------


def test_the_text_deltas_come_out_in_order_and_the_other_events_are_skipped():
    process = FakeProcess([
        event(type="stream_event", event={"type": "message_start"}),
        text_delta("Runway is "),
        event(type="stream_event", event={"type": "content_block_delta",
                                          "delta": {"type": "thinking_delta", "thinking": "hmm"}}),
        "this line is not json\n",
        text_delta("15 months."),
        event(type="result", usage={"input_tokens": 1}),
    ])

    assert list(copilot()._stream(process, "How long is your runway?")) == [
        ("text", "Runway is "),
        ("text", "15 months."),
        ("usage", {"input_tokens": 1}),
    ]


def test_the_result_ends_the_stream():
    process = FakeProcess([
        event(type="result", usage={"output_tokens": 2}),
        text_delta("never read"),
    ])

    assert list(copilot()._stream(process, "How long is your runway?")) == [("usage", {"output_tokens": 2})]
    assert process.read == [event(type="result", usage={"output_tokens": 2})]


def test_an_error_result_raises_with_its_text():
    process = FakeProcess([event(type="result", is_error=True, result="quota exceeded")])

    with pytest.raises(RuntimeError, match="Claude Code: quota exceeded"):
        list(copilot()._stream(process, "How long is your runway?"))


def test_an_error_result_without_text_raises_with_its_subtype():
    process = FakeProcess([event(type="result", is_error=True, subtype="error_max_turns")])

    with pytest.raises(RuntimeError, match="Claude Code: error_max_turns"):
        list(copilot()._stream(process, "How long is your runway?"))


def test_an_error_result_with_both_says_the_text():
    process = FakeProcess([event(type="result", is_error=True, result="quota exceeded",
                                 subtype="error_max_turns")])

    with pytest.raises(RuntimeError, match="Claude Code: quota exceeded"):
        list(copilot()._stream(process, "How long is your runway?"))


# -- the token counts -----------------------------------------------------------------------------


def test_the_token_counts_are_read():
    usage = ClaudeCodeCopilot._usage({"input_tokens": 10, "cache_creation_input_tokens": 2,
                                       "cache_read_input_tokens": 3, "output_tokens": 4})

    assert (usage.input, usage.cache_write, usage.cache_read, usage.output) == (10, 2, 3, 4)


def test_a_missing_token_count_is_zero():
    usage = ClaudeCodeCopilot._usage({"input_tokens": 10})

    assert (usage.input, usage.cache_write, usage.cache_read, usage.output) == (10, 0, 0, 0)


# -- whether Claude Code is there ----------------------------------------------------------------


def signed_in(**extra) -> str:
    return json.dumps({"loggedIn": True, "subscriptionType": "max", "authMethod": "claude.ai", **extra})


def fake_run(stdout: str):
    """A `subprocess.run` that answers with `stdout` and remembers how it was called."""
    class Result:
        pass

    result = Result()
    result.stdout = stdout
    result.stderr = ""
    result.returncode = 0
    seen = {}

    def run(command, **kwargs):
        seen["command"] = command
        seen.update(kwargs)
        return result

    return run, seen


def test_without_claude_code_installed(monkeypatch):
    monkeypatch.setattr(claude_code, "claude_path", lambda: None)

    assert claude_code.status() == {"installed": False, "signed_in": False}


def test_installed_but_the_output_is_not_json(monkeypatch):
    run, _ = fake_run("not json")
    monkeypatch.setattr(claude_code, "claude_path", lambda: "/usr/local/bin/claude")
    monkeypatch.setattr("subprocess.run", run)

    assert claude_code.status() == {"installed": True, "signed_in": False}


def test_the_plan_and_the_method_are_read(monkeypatch):
    run, _ = fake_run(signed_in())
    monkeypatch.setattr(claude_code, "claude_path", lambda: "/usr/local/bin/claude")
    monkeypatch.setattr("subprocess.run", run)

    assert claude_code.status() == {"installed": True, "signed_in": True, "plan": "max",
                                     "method": "claude.ai"}


def test_a_signed_out_claude_code_is_not_signed_in(monkeypatch):
    run, _ = fake_run(json.dumps({"loggedIn": False}))
    monkeypatch.setattr(claude_code, "claude_path", lambda: "/usr/local/bin/claude")
    monkeypatch.setattr("subprocess.run", run)

    assert claude_code.status()["signed_in"] is False


def test_the_api_key_in_the_environment_is_not_passed_on(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-secret")
    run, seen = fake_run(signed_in())
    monkeypatch.setattr(claude_code, "claude_path", lambda: "/usr/local/bin/claude")
    monkeypatch.setattr("subprocess.run", run)

    claude_code.status()

    assert seen["command"] == ["/usr/local/bin/claude", "auth", "status", "--json"]
    assert "ANTHROPIC_API_KEY" not in seen["env"]
    assert "ANTHROPIC_AUTH_TOKEN" not in seen["env"]
