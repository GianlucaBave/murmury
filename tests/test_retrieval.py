import re

import numpy as np
import pytest

from copilot.material import Source
from copilot.retrieval import (
    Chunk,
    split_sections,
    chunk_source,
    cosine_similarity,
    rank_candidates,
)


def tokenize(text):
    return [m.span() for m in re.finditer(r"\S+", text)]


def test_pdf_sections():
    source = Source(
        "demo.pdf", "pdf",
        "[page 1]\nFirst page\n\n[page 2]\nSecond page"
    )

    assert split_sections(source) == [
        ("[page 1]", "First page"),
        ("[page 2]", "Second page"),
    ]


def test_slide_sections():
    source = Source(
        "demo.pptx", "pptx",
        "[slide 1]\nIntroduction\n\n[slide 2]\nConclusion"
    )

    assert split_sections(source) == [
        ("[slide 1]", "Introduction"),
        ("[slide 2]", "Conclusion"),
    ]


def test_sheet_sections():
    source = Source(
        "demo.xlsx", "xlsx",
        "[sheet Sales]\nRevenue\n\n[sheet Costs]\nExpenses"
    )

    assert split_sections(source) == [
        ("[sheet Sales]", "Revenue"),
        ("[sheet Costs]", "Expenses"),
    ]


def test_plain_text():
    source = Source("demo.txt", "txt", "Hello world")

    assert split_sections(source) == [
        ("", "Hello world")
    ]


def test_empty_document():
    source = Source("empty.txt", "txt", "")

    assert chunk_source(source, tokenize) == []


def test_chunk_overlap():
    source = Source(
        "demo.txt", "txt",
        "One two three four five six seven eight nine ten"
    )

    chunks = chunk_source(source, tokenize, 4, 1)

    assert [c.text for c in chunks] == [
        "One two three four",
        "four five six seven",
        "seven eight nine ten",
    ]


def test_metadata_preservation():
    source = Source(
        "demo.pdf", "pdf",
        "[page 7]\nThe product costs 120 dollars."
    )

    chunks = chunk_source(source, tokenize)

    assert chunks[0].name == "demo.pdf"
    assert chunks[0].kind == "pdf"
    assert chunks[0].marker == "[page 7]"


def test_formatting_preservation():
    source = Source(
        "demo.txt", "txt",
        "Price: $120.\nAvailable in blue."
    )

    chunks = chunk_source(source, tokenize)

    assert chunks[0].text == source.text


def test_chunk_as_source():
    chunk = Chunk(
        "demo.pdf", "pdf",
        "Price is $120.", "[page 7]"
    )

    assert chunk.as_source() == Source(
        "demo.pdf", "pdf",
        "[page 7]\nPrice is $120."
    )


@pytest.mark.parametrize(
    "size, overlap",
    [(0, 0), (5, 5), (5, -1), (5, 6)]
)
def test_invalid_chunk_parameters(size, overlap):
    source = Source("demo.txt", "txt", "Hello world")

    with pytest.raises(ValueError):
        chunk_source(source, tokenize, size, overlap)


def test_cosine_similarity():
    query = np.array([1, 0])
    embeddings = np.array([
        [1, 0],
        [0, 1],
        [-1, 0],
    ])

    scores = cosine_similarity(query, embeddings)

    np.testing.assert_allclose(scores, [1, 0, -1])


def test_zero_embedding():
    query = np.array([1, 0])
    embeddings = np.array([[0, 0]])

    scores = cosine_similarity(query, embeddings)

    np.testing.assert_allclose(scores, [0])


def test_zero_query():
    query = np.array([0, 0])
    embeddings = np.array([[1, 0], [0, 1]])

    scores = cosine_similarity(query, embeddings)

    np.testing.assert_allclose(scores, [0, 0])


def test_rank_candidates():
    query = np.array([1, 0])
    embeddings = np.array([
        [0, 1],
        [1, 0],
        [0.8, 0.2],
    ])

    assert rank_candidates(query, embeddings) == [1, 2, 0]


def test_top_k_limit():
    query = np.array([1, 0])
    embeddings = np.array([
        [0, 1],
        [1, 0],
        [0.8, 0.2],
    ])

    assert rank_candidates(query, embeddings, 2) == [1, 2]


def test_empty_embeddings():
    query = np.array([1, 0])
    embeddings = np.empty((0, 2))

    assert rank_candidates(query, embeddings) == []


def test_zero_top_k():
    query = np.array([1, 0])
    embeddings = np.array([[1, 0]])

    assert rank_candidates(query, embeddings, 0) == []


def test_equal_similarity():
    query = np.array([1, 0])
    embeddings = np.array([
        [1, 0],
        [1, 0],
        [1, 0],
    ])

    assert rank_candidates(query, embeddings) == [0, 1, 2]