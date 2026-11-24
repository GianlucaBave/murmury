import re

import numpy as np
import pytest

from copilot.material import Source
from copilot.retrieval import (
    Chunk,
    RetrievalIndex,
    split_sections,
    chunk_source,
    cosine_similarity,
    rank_candidates,
)


def tokenize(text):
    return [m.span() for m in re.finditer(r"\S+", text)]


def test_pdf_sections():
    source = Source(
        "demo.pdf",
        "pdf",
        "[page 1]\nFirst page\n\n[page 2]\nSecond page",
    )

    assert split_sections(source) == [
        ("[page 1]", "First page"),
        ("[page 2]", "Second page"),
    ]


def test_slide_sections():
    source = Source(
        "demo.pptx",
        "pptx",
        "[slide 1]\nIntroduction\n\n[slide 2]\nConclusion",
    )

    assert split_sections(source) == [
        ("[slide 1]", "Introduction"),
        ("[slide 2]", "Conclusion"),
    ]


def test_sheet_sections():
    source = Source(
        "demo.xlsx",
        "xlsx",
        "[sheet Sales]\nRevenue\n\n[sheet Costs]\nExpenses",
    )

    assert split_sections(source) == [
        ("[sheet Sales]", "Revenue"),
        ("[sheet Costs]", "Expenses"),
    ]


def test_plain_text():
    source = Source("demo.txt", "txt", "Hello world")
    assert split_sections(source) == [("", "Hello world")]


def test_empty_document():
    source = Source("empty.txt", "txt", "")
    assert chunk_source(source, tokenize) == []


def test_chunk_overlap():
    source = Source(
        "demo.txt",
        "txt",
        "One two three four five six seven eight nine ten",
    )

    chunks = chunk_source(source, tokenize, 4, 1)

    assert [c.text for c in chunks] == [
        "One two three four",
        "four five six seven",
        "seven eight nine ten",
    ]


def test_metadata_preservation():
    source = Source(
        "demo.pdf",
        "pdf",
        "[page 7]\nThe product costs 120 dollars.",
    )

    chunks = chunk_source(source, tokenize)

    assert chunks[0].name == "demo.pdf"
    assert chunks[0].kind == "pdf"
    assert chunks[0].marker == "[page 7]"


def test_formatting_preservation():
    source = Source(
        "demo.txt",
        "txt",
        "Price: $120.\nAvailable in blue.",
    )

    chunks = chunk_source(source, tokenize)

    assert chunks[0].text == source.text


def test_chunk_as_source():
    chunk = Chunk(
        "demo.pdf",
        "pdf",
        "Price is $120.",
        "[page 7]",
    )

    assert chunk.as_source() == Source(
        "demo.pdf",
        "pdf",
        "[page 7]\nPrice is $120.",
    )


@pytest.mark.parametrize(
    "size, overlap",
    [(0, 0), (5, 5), (5, -1), (5, 6)],
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


def make_index():
    chunks = [
        Chunk("demo.pdf", "pdf", "Apple price is 120", "[page 1]"),
        Chunk("demo.pdf", "pdf", "Banana price is 80", "[page 2]"),
        Chunk("demo.pdf", "pdf", "Orange price is 100", "[page 3]"),
    ]

    embeddings = np.array([
        [1, 0],
        [0, 1],
        [0.8, 0.2],
    ])

    def embed_query(question):
        return np.array([1, 0])

    def rerank(question, texts):
        return [
            1.0 if "Orange" in text else 0.5
            for text in texts
        ]

    return RetrievalIndex(
        chunks,
        embeddings,
        embed_query,
        rerank,
    )


def test_retrieval_reranking():
    index = make_index()
    results = index.retrieve("Orange price")

    assert results[0].marker == "[page 3]"


def test_retrieval_candidate_limit():
    index = make_index()
    results = index.retrieve("Price", top_k=1)

    assert len(results) == 1
    assert results[0].marker == "[page 1]"


def test_retrieval_final_limit():
    index = make_index()
    results = index.retrieve("Price", final_k=2)

    assert len(results) == 2


def test_retrieval_empty_index():
    index = RetrievalIndex(
        [],
        np.empty((0, 2)),
        lambda question: np.array([1, 0]),
        lambda question, texts: [],
    )

    assert index.retrieve("Price") == []


def test_retrieval_invalid_embeddings():
    with pytest.raises(ValueError):
        RetrievalIndex(
            [Chunk("demo.txt", "txt", "Hello")],
            np.empty((0, 2)),
            lambda question: np.array([1, 0]),
            lambda question, texts: [],
        )


def test_invalid_reranking_scores():
    index = make_index()
    index.rerank = lambda question, texts: []

    with pytest.raises(ValueError):
        index.retrieve("Price")


def test_retrieval_prompt_metadata():
    index = make_index()

    prompt = index.retrieve_prompt(
        "Orange price",
        lambda text: len(text.split()),
        100,
    )

    assert "demo.pdf" in prompt
    assert "[page 3]" in prompt
    assert "Orange price is 100" in prompt


def test_retrieval_token_budget():
    index = make_index()
    count_tokens = lambda text: len(text.split())

    prompt = index.retrieve_prompt(
        "Price",
        count_tokens,
        10,
    )

    assert "Orange price is 100" in prompt
    assert count_tokens(prompt) <= 10


def test_retrieval_zero_budget():
    index = make_index()

    assert index.retrieve_prompt(
        "Price",
        lambda text: len(text.split()),
        0,
    ) == ""


def test_retrieval_insufficient_budget():
    index = make_index()

    assert index.retrieve_prompt(
        "Price",
        lambda text: len(text.split()),
        1,
    ) == ""