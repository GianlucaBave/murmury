import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from copilot.fastembed_backend import (
    EMBEDDING_MODEL,
    RERANKER_MODEL,
    FastEmbedBackend,
)
from copilot.material import Source


@pytest.fixture
def backend():
    embedding = MagicMock()
    reranker = MagicMock()
    tokenizer = MagicMock()

    embedding.model.tokenizer.to_str.return_value = "{}"

    embedding.embed.side_effect = lambda texts: iter(
        [[1.0, 0.0] for _ in texts]
    )

    embedding.query_embed.return_value = iter(
        [[1.0, 0.0]]
    )

    reranker.rerank.return_value = iter([0.9, 0.4])

    def encode(text, add_special_tokens=False):
        import re

        result = MagicMock()
        result.offsets = [
            match.span()
            for match in re.finditer(r"\S+", text)
        ]
        return result

    tokenizer.encode.side_effect = encode

    fastembed = MagicMock()
    fastembed.TextEmbedding.return_value = embedding

    cross_encoder = MagicMock()
    cross_encoder.TextCrossEncoder.return_value = reranker

    tokenizers = MagicMock()
    tokenizers.Tokenizer.from_str.return_value = tokenizer

    with patch.dict(
        sys.modules,
        {
            "fastembed": fastembed,
            "fastembed.rerank": MagicMock(),
            "fastembed.rerank.cross_encoder": cross_encoder,
            "tokenizers": tokenizers,
        },
    ):
        instance = FastEmbedBackend()

    return instance, fastembed, cross_encoder, tokenizer


def test_embedding_model_selection(backend):
    _, fastembed, _, _ = backend

    fastembed.TextEmbedding.assert_called_once_with(
        model_name=EMBEDDING_MODEL,
        cuda=False,
    )


def test_reranker_model_selection(backend):
    _, _, cross_encoder, _ = backend

    cross_encoder.TextCrossEncoder.assert_called_once_with(
        model_name=RERANKER_MODEL,
        cuda=False,
    )


def test_tokenizer_disables_truncation_and_padding(backend):
    _, _, _, tokenizer = backend

    tokenizer.no_truncation.assert_called_once()
    tokenizer.no_padding.assert_called_once()


def test_tokenizer_returns_offsets(backend):
    instance, _, _, _ = backend

    assert instance.tokenize("hello world") == [
        (0, 5),
        (6, 11),
    ]


def test_count_tokens(backend):
    instance, _, _, _ = backend

    assert instance.count_tokens("one two three") == 3


def test_long_document_tokenization(backend):
    instance, _, _, _ = backend

    text = " ".join(["word"] * 1200)

    assert instance.count_tokens(text) == 1200


def test_embed_documents(backend):
    instance, _, _, _ = backend

    result = instance.embed_documents(["one", "two"])

    np.testing.assert_array_equal(
        result,
        [[1.0, 0.0], [1.0, 0.0]],
    )


def test_embed_query(backend):
    instance, _, _, _ = backend

    result = instance.embed_query("question")

    np.testing.assert_array_equal(result, [1.0, 0.0])


def test_rerank(backend):
    instance, _, _, _ = backend

    assert instance.rerank(
        "question",
        ["one", "two"],
    ) == [0.9, 0.4]


def test_build_index_preserves_metadata(backend):
    instance, _, _, _ = backend

    sources = [
        Source(
            "report.pdf",
            "pdf",
            "[page 3]\nRevenue increased",
        )
    ]

    index = instance.build_index(sources)

    assert len(index.chunks) == 1
    assert index.chunks[0].name == "report.pdf"
    assert index.chunks[0].marker == "[page 3]"
    assert index.chunks[0].text == "Revenue increased"


def test_build_index_chunks_long_documents(backend):
    instance, _, _, _ = backend

    text = " ".join(["word"] * 1200)

    index = instance.build_index(
        [Source("report.txt", "text", text)]
    )

    assert len(index.chunks) == 3
    assert index.embeddings.shape == (3, 2)


def test_build_empty_index(backend):
    instance, _, _, _ = backend

    index = instance.build_index([])

    assert index.chunks == []
    assert index.retrieve("question") == []
    instance.embedding.embed.assert_not_called()