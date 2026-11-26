from __future__ import annotations

import numpy as np

from .material import Source
from .retrieval import RetrievalIndex, chunk_source


EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


class FastEmbedBackend:
    def __init__(self):
        from fastembed import TextEmbedding
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        from tokenizers import Tokenizer

        self.embedding = TextEmbedding(
            model_name=EMBEDDING_MODEL,
            cuda=False,
        )

        tokenizer = self.embedding.model.tokenizer

        if tokenizer is None:
            raise RuntimeError("Embedding tokenizer is unavailable")

        self.tokenizer = Tokenizer.from_str(
            tokenizer.to_str()
        )

        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()

        self.reranker = TextCrossEncoder(
            model_name=RERANKER_MODEL,
            cuda=False,
        )

    def tokenize(self, text: str) -> list[tuple[int, int]]:
        return self.tokenizer.encode(
            text,
            add_special_tokens=False,
        ).offsets

    def count_tokens(self, text: str) -> int:
        return len(self.tokenize(text))

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            list(self.embedding.embed(texts)),
            dtype=float,
        )

    def embed_query(self, question: str) -> np.ndarray:
        return np.asarray(
            next(iter(self.embedding.query_embed(question))),
            dtype=float,
        )

    def rerank(self, question: str, texts: list[str]) -> list[float]:
        return list(self.reranker.rerank(question, texts))

    def build_index(self, sources: list[Source]) -> RetrievalIndex:
        chunks = [
            chunk
            for source in sources
            for chunk in chunk_source(source, self.tokenize)
        ]

        texts = [chunk.text for chunk in chunks]

        embeddings = (
            self.embed_documents(texts)
            if texts
            else np.empty((0, 0))
        )

        return RetrievalIndex(
            chunks=chunks,
            embeddings=embeddings,
            embed_query=self.embed_query,
            rerank=self.rerank,
        )