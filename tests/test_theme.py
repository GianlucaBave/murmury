import ast
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from copilot import theme
from copilot.setup import settings_store

_app = QApplication.instance() or QApplication([])

COPILOT_DIR = Path(theme.__file__).parent
TOKEN = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """Every test writes to the test preferences, never to the real Murmury ones."""
    monkeypatch.setenv("MURMURY_TEST_SETTINGS", "1")
    store = settings_store()
    assert store.organizationName() == "Murmury-test"  # safety net
    store.remove("appearance")
    store.sync()
    yield store
    store.remove("appearance")
    store.sync()
    theme.set_dark(False, remember=False)  # leave the app as we found it


def stylesheet_tokens() -> set[str]:
    """Every $token in the string constants (docstrings excluded) of the files that call fill()."""
    tokens = set()
    for path in COPILOT_DIR.glob("*.py"):
        if path.name == "theme.py":
            continue
        source = path.read_text(encoding="utf-8")
        if "fill(" not in source:
            continue
        tree = ast.parse(source)
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                      and node.body and isinstance(node.body[0], ast.Expr)
                      and isinstance(node.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                tokens |= set(TOKEN.findall(node.value))
    return tokens


# ---------- palettes ----------

def test_light_and_dark_have_the_same_keys():
    assert set(theme.LIGHT) == set(theme.DARK)


def test_every_stylesheet_token_has_a_colour_in_both_palettes():
    tokens = stylesheet_tokens()
    assert tokens, "no $tokens found: the scan is broken"
    assert tokens - set(theme.LIGHT) == set(), "tokens missing from LIGHT"
    assert tokens - set(theme.DARK) == set(), "tokens missing from DARK"


# ---------- saving the appearance ----------

def test_set_dark_true_saves_dark(test_settings):
    theme.set_dark(True)
    test_settings.sync()
    assert test_settings.value("appearance") == "dark"


def test_set_dark_false_saves_light(test_settings):
    theme.set_dark(False)
    test_settings.sync()
    assert test_settings.value("appearance") == "light"


def test_set_dark_without_remember_saves_nothing(test_settings):
    theme.set_dark(False, remember=False)
    test_settings.sync()
    assert test_settings.value("appearance") is None


@pytest.mark.parametrize("saved, expected", [("dark", True), ("light", False)])
def test_apply_saved_reads_the_value_back(monkeypatch, test_settings, saved, expected):
    calls = []
    monkeypatch.setattr(theme, "set_dark", lambda dark, remember=True: calls.append((dark, remember)))
    test_settings.setValue("appearance", saved)
    theme.apply_saved()
    assert calls == [(expected, False)]


def test_apply_saved_does_nothing_when_nothing_is_saved(monkeypatch):
    calls = []
    monkeypatch.setattr(theme, "set_dark", lambda *a, **k: calls.append(a))
    theme.apply_saved()
    assert calls == []