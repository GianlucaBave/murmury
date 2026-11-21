"""count_answered_call() counts calls where Murmury answered something, and a bad stored value can't break it."""
import pytest

from copilot import app
from copilot.setup import answered_calls, settings_store


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("MURMURY_TEST_SETTINGS", "1")  # never touch the real preferences
    store = settings_store()
    store.remove("answered_calls")
    app.ANSWERED.clear()
    yield store
    store.remove("answered_calls")
    app.ANSWERED.clear()


def test_nothing_answered_leaves_count_unchanged(store):
    app.count_answered_call()
    assert answered_calls(store) == 0
    store.setValue("answered_calls", 3)
    app.count_answered_call()
    assert answered_calls(store) == 3


def test_answered_call_goes_from_nothing_to_one(store):
    app.ANSWERED.set()
    app.count_answered_call()
    assert answered_calls(store) == 1


def test_answered_call_goes_from_one_to_two(store):
    store.setValue("answered_calls", 1)
    app.ANSWERED.set()
    app.count_answered_call()
    assert answered_calls(store) == 2


@pytest.mark.parametrize("bad", ["abc", "", "1.5"])
def test_bad_stored_value_counts_as_zero(store, bad):
    store.setValue("answered_calls", bad)
    assert answered_calls(store) == 0


@pytest.mark.parametrize("bad", ["abc", ""])
def test_next_call_stores_one_instead_of_raising(store, bad):
    store.setValue("answered_calls", bad)
    app.ANSWERED.set()
    app.count_answered_call()
    assert answered_calls(store) == 1


def test_helper_reads_what_count_stored(store):
    app.ANSWERED.set()
    app.count_answered_call()
    assert int(store.value("answered_calls")) == 1
    assert answered_calls(store) == 1