"""Tests for Usage.add() and the eval cost() function.

These cover the token accounting in copilot/answer.py and the price calculation
in evals/run.py. No network or API keys are required.
"""

from types import SimpleNamespace

from copilot.answer import Usage
from evals.run import PRICES, cost


def _usage(**kwargs) -> SimpleNamespace:
    """Build a stand-in for anthropic.types.Usage with the fields add() reads."""
    defaults = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_new_usage_is_all_zeros():
    u = Usage()
    assert u.input == 0
    assert u.cache_write == 0
    assert u.cache_read == 0
    assert u.output == 0


def test_add_sums_each_field():
    u = Usage()
    u.add(_usage(input_tokens=10, output_tokens=5, cache_creation_input_tokens=2, cache_read_input_tokens=3))
    u.add(_usage(input_tokens=20, output_tokens=7, cache_creation_input_tokens=4, cache_read_input_tokens=1))
    assert u.input == 30
    assert u.output == 12
    assert u.cache_write == 6
    assert u.cache_read == 4


def test_add_treats_none_cache_fields_as_zero():
    u = Usage()
    u.add(_usage(input_tokens=10, output_tokens=5,
                 cache_creation_input_tokens=None,
                 cache_read_input_tokens=None))
    assert u.input == 10
    assert u.output == 5
    assert u.cache_write == 0
    assert u.cache_read == 0


def test_cost_matches_prices_field_by_field():
    model = "claude-haiku-4-5"
    i, w, r, o = PRICES[model]
    # one field at a time
    assert cost(model, Usage(input=1_000_000)) == i
    assert cost(model, Usage(cache_write=1_000_000)) == w
    assert cost(model, Usage(cache_read=1_000_000)) == r
    assert cost(model, Usage(output=1_000_000)) == o


def test_cost_unknown_model_is_zero():
    u = Usage(input=1_000_000, cache_write=1_000_000, cache_read=1_000_000, output=1_000_000)
    assert cost("unknown-model", u) == 0.0


def test_cost_scales_with_token_count():
    model = "claude-sonnet-5-5"
    i, w, r, o = PRICES[model]
    u = Usage(input=500_000, cache_write=200_000, cache_read=100_000, output=50_000)
    expected = (500_000 * i + 200_000 * w + 100_000 * r + 50_000 * o) / 1e6
    assert cost(model, u) == expected
