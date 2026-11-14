from pathlib import Path

import pytest

from copilot import setup


@pytest.fixture(autouse=True)
def mock_dictionary(monkeypatch):
    monkeypatch.setattr(setup, "_dictionary", lambda: set())


def suggest(tmp_path: Path, text: str, limit: int = 20) -> str:
    document = tmp_path / "document.txt"
    document.write_text(text, encoding="utf-8")
    return setup.suggest_vocabulary([document], limit=limit)


def repeated(word: str, count: int) -> str:
    return " ".join([word] * count)


def test_suggests_names_repeated_at_least_three_times(tmp_path):
    text = f"{repeated('Acme', 3)} {repeated('Globex', 2)}"

    result = suggest(tmp_path, text)

    assert result == "Acme"


def test_excludes_names_with_frequent_lowercase_occurrences(tmp_path):
    text = f"{repeated('Acme', 4)} acme"

    result = suggest(tmp_path, text)

    assert result == ""


def test_filters_dictionary_words_and_inflections(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "_dictionary", lambda: {"report", "plan"})
    text = f"{repeated('Report', 3)} {repeated('Plans', 3)} {repeated('Acme', 3)}"

    result = suggest(tmp_path, text)

    assert result == "Acme"


def test_excludes_months_and_words_of_two_letters(tmp_path):
    text = " ".join([
        repeated("January", 3),
        repeated("Jan", 3),
        repeated("Sept", 3),
        repeated("AI", 3),
        repeated("Acme", 3),
    ])

    result = suggest(tmp_path, text)

    assert result == "January, Acme"


def test_keeps_acronyms_and_orders_by_frequency(tmp_path):
    text = " ".join([
        repeated("ARR", 5),
        repeated("Acme", 4),
        repeated("Globex", 3),
    ])

    result = suggest(tmp_path, text)

    assert result == "ARR, Acme, Globex"


def test_respects_result_limit(tmp_path):
    text = " ".join([
        repeated("Alpha", 5),
        repeated("Beta", 4),
        repeated("Gamma", 3),
    ])

    result = suggest(tmp_path, text, limit=2)

    assert result == "Alpha, Beta"
