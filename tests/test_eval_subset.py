from copilot.material import Source
from evals.run import subset


PDF_TEXT = (
    "[page 1]\nRevenue 2025\n\n"
    "[page 2]\nTeam\n\n"
    "[page 3]\nRunway 18 months"
)


def make_source(kind="pdf", text=PDF_TEXT):
    return Source(
        name="report.pdf",
        kind=kind,
        text=text,
    )


def test_non_pdf_source_is_returned_unchanged():
    source = make_source(kind="text")

    result = subset(source, pages={1, 3}, keywords=["runway"])

    assert result is source


def test_pdf_without_filters_is_returned_unchanged():
    source = make_source()

    result = subset(source, pages=None, keywords=[])

    assert result is source


def test_selected_pages_are_kept_in_order():
    source = make_source()

    result = subset(source, pages={1, 3}, keywords=[])

    assert result.text == (
        "[page 1]\nRevenue 2025\n\n"
        "[page 3]\nRunway 18 months"
    )
    assert "[page 1]" in result.text
    assert "[page 3]" in result.text
    assert "[page 2]" not in result.text


def test_keyword_matching_is_case_insensitive():
    source = make_source()

    result = subset(source, pages=None, keywords=["runway"])

    assert result.text == "[page 3]\nRunway 18 months"


def test_pages_and_keywords_keep_their_union_without_duplicates():
    source = make_source()

    result = subset(
        source,
        pages={1, 3},
        keywords=["team", "runway"],
    )

    expected = (
        "[page 1]\nRevenue 2025\n\n"
        "[page 2]\nTeam\n\n"
        "[page 3]\nRunway 18 months"
    )

    assert result.text == expected
    assert result.text.count("[page 1]") == 1
    assert result.text.count("[page 2]") == 1
    assert result.text.count("[page 3]") == 1


def test_nonexistent_page_returns_empty_text():
    source = make_source()

    result = subset(source, pages={99}, keywords=[])

    assert result.text == ""


def test_unmatched_keyword_returns_empty_text():
    source = make_source()

    result = subset(source, pages=None, keywords=["nonexistent"])

    assert result.text == ""