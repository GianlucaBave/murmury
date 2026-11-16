"""Tests for Usage.add() in copilot.answer and cost() in evals.run (#80)."""

from types import SimpleNamespace

import pytest

from copilot.answer import Usage
from evals.run import PRICES, cost


def test_new_usage_is_all_zeros():
    u = Usage()
    assert u.input == 0
    assert u.cache_write == 0
    assert u.cache_read == 0
    assert u.output == 0


def test_usage_add_sums_each_field():
    u = Usage()
    resp1 = SimpleNamespace(
        input_tokens=100,
        cache_creation_input_tokens=20,
        cache_read_input_tokens=10,
        output_tokens=30,
    )
    resp2 = SimpleNamespace(
        input_tokens=250,
        cache_creation_input_tokens=15,
        cache_read_input_tokens=40,
        output_tokens=80,
    )

    u.add(resp1)
    assert u.input == 100
    assert u.cache_write == 20
    assert u.cache_read == 10
    assert u.output == 30

    u.add(resp2)
    assert u.input == 350
    assert u.cache_write == 35
    assert u.cache_read == 50
    assert u.output == 110


def test_usage_add_treats_none_cache_tokens_as_zero():
    u = Usage()
    resp = SimpleNamespace(
        input_tokens=150,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
        output_tokens=45,
    )

    u.add(resp)
    assert u.input == 150
    assert u.cache_write == 0
    assert u.cache_read == 0
    assert u.output == 45


def test_usage_add_mixed_none_and_integer_cache_tokens():
    u = Usage()
    resp1 = SimpleNamespace(
        input_tokens=100,
        cache_creation_input_tokens=50,
        cache_read_input_tokens=None,
        output_tokens=25,
    )
    resp2 = SimpleNamespace(
        input_tokens=200,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=80,
        output_tokens=60,
    )

    u.add(resp1)
    assert u.cache_write == 50
    assert u.cache_read == 0

    u.add(resp2)
    assert u.cache_write == 50
    assert u.cache_read == 80


@pytest.mark.parametrize("model", list(PRICES.keys()))
def test_cost_matches_price_per_million_input_tokens(model):
    price_input, _, _, _ = PRICES[model]
    u = Usage(input=1_000_000, cache_write=0, cache_read=0, output=0)
    assert cost(model, u) == pytest.approx(price_input)


@pytest.mark.parametrize("model", list(PRICES.keys()))
def test_cost_matches_price_per_million_cache_write_tokens(model):
    _, price_write, _, _ = PRICES[model]
    u = Usage(input=0, cache_write=1_000_000, cache_read=0, output=0)
    assert cost(model, u) == pytest.approx(price_write)


@pytest.mark.parametrize("model", list(PRICES.keys()))
def test_cost_matches_price_per_million_cache_read_tokens(model):
    _, _, price_read, _ = PRICES[model]
    u = Usage(input=0, cache_write=0, cache_read=1_000_000, output=0)
    assert cost(model, u) == pytest.approx(price_read)


@pytest.mark.parametrize("model", list(PRICES.keys()))
def test_cost_matches_price_per_million_output_tokens(model):
    _, _, _, price_output = PRICES[model]
    u = Usage(input=0, cache_write=0, cache_read=0, output=1_000_000)
    assert cost(model, u) == pytest.approx(price_output)


def test_cost_combined_tokens():
    # claude-sonnet-5-5: (2.0, 2.5, 0.2, 10.0)
    u = Usage(input=10_000, cache_write=5_000, cache_read=20_000, output=1_000)
    assert cost("claude-sonnet-5-5", u) == pytest.approx(0.0465)


def test_cost_for_unlisted_model_is_zero():
    u = Usage(input=100_000, cache_write=50_000, cache_read=20_000, output=10_000)
    assert cost("unknown-model", u) == 0.0
    assert cost("gpt-4o", u) == 0.0
