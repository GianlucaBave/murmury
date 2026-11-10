
from dataclasses import replace
import re

import pytest

from copilot.answer import FORMATS, PRESETS, TONES, Style, instructions


SITUATION = "a project review meeting"


def make_prompt(style=None):
    return instructions(SITUATION, style or Style())


def get_slots(prompt):
    section = prompt.split("Format, exactly:\n", 1)[1]
    section = section.split("\nNothing more:", 1)[0]
    return [line for line in section.splitlines() if line.startswith("- ")]


def test_default_style():
    prompt = make_prompt()
    slots = get_slots(prompt)

    assert "SAY: one sentence of at most 12 plain spoken words" in prompt
    assert len(slots) == 3
    assert all(line.endswith("[source]") for line in slots)


def test_single_line():
    prompt = make_prompt(Style(lines=1))

    assert "one line under the SAY line" in prompt
    assert len(get_slots(prompt)) == 1


def test_custom_word_limits():
    prompt = make_prompt(Style(say_words=7, line_words=9))

    assert "SAY: one sentence of at most 7 plain spoken words" in prompt
    assert all("at most 9 words" in line for line in get_slots(prompt))


@pytest.mark.parametrize(
    "count, expected",
    [(0, "no numbers"), (2, "at most 2 numbers")],
)
def test_number_limits(count, expected):
    prompt = make_prompt(Style(numbers=count))

    assert all(expected in line for line in get_slots(prompt))


def test_sources_disabled():
    prompt = make_prompt(Style(sources=False))

    assert not re.search(
        r"\[(?:source|§[^\]]*|Table [^\]]*|Figure [^\]]*)\]",
        prompt,
    )


def test_italian_language():
    prompt = make_prompt(Style(language="Italian"))

    assert "Write the answer in Italian" in prompt
    assert "Always answer in Italian" in prompt


def test_default_language():
    prompt = make_prompt(Style(language=""))

    assert "Answer in the language of the question" in prompt


@pytest.mark.parametrize("tone", list(TONES))
def test_supported_tones(tone):
    prompt = make_prompt(Style(tone=tone))

    assert TONES[tone] in prompt


def test_unknown_tone_fallback():
    prompt = make_prompt(Style(tone="unknown"))

    assert TONES["confident"] in prompt


def test_unknown_format_fallback():
    prompt = make_prompt(Style(format="unknown"))

    assert prompt == make_prompt(Style(format="talking"))


def test_custom_extra_instructions():
    prompt = make_prompt(Style(extra="Keep the answer concise"))

    assert "Keep the answer concise" in prompt


@pytest.mark.parametrize("extra", ["", "   ", "\n\t"])
def test_blank_extra_instructions(extra):
    assert make_prompt(Style(extra=extra)) == make_prompt()


@pytest.mark.parametrize("preset", list(PRESETS))
@pytest.mark.parametrize("format_name", list(FORMATS))
def test_presets_and_formats_have_no_unresolved_braces(preset, format_name):
    style = replace(PRESETS[preset], format=format_name)
    prompt = make_prompt(style)

    assert "{" not in prompt
    assert "}" not in prompt
