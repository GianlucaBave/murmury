import pytest

from evals.run import page_set


@pytest.mark.parametrize("spec", [None, ""])
def test_no_spec_means_all_pages(spec):
    assert page_set(spec) is None


def test_a_single_page():
    assert page_set("3") == {3}


def test_a_range_and_a_single_page():
    assert page_set("1-3,7") == {1, 2, 3, 7}


def test_a_range_includes_both_ends():
    assert page_set("2-4") == {2, 3, 4}


def test_a_range_of_one_page():
    assert page_set("5-5") == {5}


def test_overlapping_ranges_give_each_page_once():
    assert page_set("1-3,2-4") == {1, 2, 3, 4}


def test_a_repeated_page_is_kept_once():
    assert page_set("2,2") == {2}


def test_spaces_around_the_numbers_are_ignored():
    assert page_set(" 1 - 2 ") == {1, 2}
    assert page_set("1 , 3") == {1, 3}


@pytest.mark.parametrize("spec", ["a", "1-b", "x-3", "1,,3"])
def test_text_that_is_not_a_number_raises(spec):
    with pytest.raises(ValueError):
        page_set(spec)


def test_a_backwards_range_raises_and_names_the_range():
    with pytest.raises(ValueError, match="3-1"):
        page_set("3-1")
