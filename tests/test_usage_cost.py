from types import SimpleNamespace

import pytest

from copilot.answer import Usage
from evals.run import PRICES, cost

MODEL = "claude-sonnet-5-5"
FIELDS = ("input", "cache_write", "cache_read", "output")


def api_usage(input_tokens=0, output_tokens=0, cache_write=0, cache_read=0):
    """What the API returns with a response; the cache fields can be None."""
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_write,
        cache_read_input_tokens=cache_read,
    )


def test_new_usage_is_all_zeros():
    usage = Usage()

    assert (usage.input, usage.cache_write, usage.cache_read, usage.output) == (0, 0, 0, 0)


def test_add_copies_each_field_from_the_response():
    usage = Usage()

    usage.add(api_usage(input_tokens=100, output_tokens=40, cache_write=300, cache_read=2000))

    assert usage == Usage(input=100, cache_write=300, cache_read=2000, output=40)


def test_add_twice_sums_each_field():
    usage = Usage()

    usage.add(api_usage(input_tokens=100, output_tokens=40, cache_write=300, cache_read=2000))
    usage.add(api_usage(input_tokens=7, output_tokens=5, cache_write=11, cache_read=13))

    assert usage == Usage(input=107, cache_write=311, cache_read=2013, output=45)


def test_none_cache_write_counts_as_zero():
    usage = Usage()

    usage.add(api_usage(input_tokens=10, output_tokens=2, cache_write=None, cache_read=50))

    assert usage == Usage(input=10, cache_write=0, cache_read=50, output=2)


def test_none_cache_read_counts_as_zero():
    usage = Usage()

    usage.add(api_usage(input_tokens=10, output_tokens=2, cache_write=50, cache_read=None))

    assert usage == Usage(input=10, cache_write=50, cache_read=0, output=2)


def test_none_cache_fields_keep_the_running_total():
    usage = Usage(input=1, cache_write=20, cache_read=30, output=4)

    usage.add(api_usage(input_tokens=1, output_tokens=1, cache_write=None, cache_read=None))

    assert usage == Usage(input=2, cache_write=20, cache_read=30, output=5)


@pytest.mark.parametrize("field", FIELDS)
def test_cost_of_a_million_tokens_is_the_listed_price(field):
    price = PRICES[MODEL][FIELDS.index(field)]

    assert cost(MODEL, Usage(**{field: 1_000_000})) == pytest.approx(price)


@pytest.mark.parametrize("field", FIELDS)
def test_cost_scales_with_the_token_count(field):
    price = PRICES[MODEL][FIELDS.index(field)]

    assert cost(MODEL, Usage(**{field: 2_500})) == pytest.approx(price * 2_500 / 1e6)


def test_cost_adds_the_four_fields():
    i, w, r, o = PRICES[MODEL]
    usage = Usage(input=1_000, cache_write=2_000, cache_read=30_000, output=400)

    assert cost(MODEL, usage) == pytest.approx((1_000 * i + 2_000 * w + 30_000 * r + 400 * o) / 1e6)


@pytest.mark.parametrize("model", sorted(PRICES))
def test_every_listed_model_is_priced(model):
    usage = Usage(input=1_000_000, cache_write=1_000_000, cache_read=1_000_000, output=1_000_000)

    assert cost(model, usage) == pytest.approx(sum(PRICES[model]))


def test_cost_of_zero_usage_is_zero():
    assert cost(MODEL, Usage()) == 0.0


def test_cost_of_an_unknown_model_is_zero():
    usage = Usage(input=1_000_000, cache_write=1_000_000, cache_read=1_000_000, output=1_000_000)

    assert cost("not-a-model", usage) == 0.0
