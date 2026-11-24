from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from .material import Source, as_prompt


CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
RETRIEVAL_TOP_K = 20
RERANK_TOP_K = 5


@dataclass(frozen=True)
class Chunk:
    name: str
    kind: str
    text: str
    marker: str = ""

    def as_source(self) -> Source:
        text = (
            f"{self.marker}\n{self.text}"
            if self.marker
            else self.text
        )
        return Source(self.name, self.kind, text)


MARKER_PATTERN = re.compile(
    r"^\[(?:page \d+|slide \d+|sheet [^\]\n]+)\][ \t]*$",
    re.MULTILINE
)


def split_sections(source: Source) -> list[tuple[str, str]]:
    sections = []
    marker = ""
    start = 0

    for match in MARKER_PATTERN.finditer(source.text):
        text = source.text[start:match.start()].strip()

        if text:
            sections.append((marker, text))

        marker = match.group().strip()
        start = match.end()

    text = source.text[start:].strip()

    if text:
        sections.append((marker, text))

    return sections


def chunk_source(
    source: Source,
    tokenize: Callable[[str], list[tuple[int, int]]],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:

    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError("Invalid chunk size or overlap")

    chunks = []

    for marker, text in split_sections(source):
        offsets = tokenize(text)
        start = 0

        while start < len(offsets):
            end = min(start + chunk_size, len(offsets))

            char_start = offsets[start][0]
            char_end = offsets[end - 1][1]

            chunks.append(
                Chunk(
                    name=source.name,
                    kind=source.kind,
                    text=text[char_start:char_end],
                    marker=marker,
                )
            )

            if end == len(offsets):
                break

            start = end - overlap

    return chunks


def cosine_similarity(
    query: np.ndarray,
    embeddings: np.ndarray,
) -> np.ndarray:

    query = np.asarray(query, dtype=float)
    embeddings = np.asarray(embeddings, dtype=float)

    query_norm = np.linalg.norm(query)
    embedding_norms = np.linalg.norm(embeddings, axis=1)

    denominator = query_norm * embedding_norms

    return np.divide(
        embeddings @ query,
        denominator,
        out=np.zeros(len(embeddings)),
        where=denominator != 0,
    )


def rank_candidates(
    query: np.ndarray,
    embeddings: np.ndarray,
    top_k: int = RETRIEVAL_TOP_K,
) -> list[int]:

    if top_k <= 0 or len(embeddings) == 0:
        return []

    scores = cosine_similarity(query, embeddings)

    return np.argsort(-scores, kind="stable")[:top_k].tolist()


class RetrievalIndex:
    def __init__(
        self,
        chunks: list[Chunk],
        embeddings: np.ndarray,
        embed_query: Callable[[str], np.ndarray],
        rerank: Callable[[str, list[str]], list[float]],
    ):
        self.chunks = list(chunks)
        self.embeddings = np.asarray(embeddings, dtype=float)
        self.embed_query = embed_query
        self.rerank = rerank

        if len(self.chunks) != len(self.embeddings):
            raise ValueError("Chunk and embedding counts must match")

    def retrieve(
        self,
        question: str,
        top_k: int = RETRIEVAL_TOP_K,
        final_k: int = RERANK_TOP_K,
    ) -> list[Chunk]:

        if not self.chunks or top_k <= 0 or final_k <= 0:
            return []

        query = self.embed_query(question)

        indices = rank_candidates(
            query,
            self.embeddings,
            top_k,
        )

        candidates = [self.chunks[i] for i in indices]

        texts = [
            chunk.as_source().text
            for chunk in candidates
        ]

        scores = self.rerank(question, texts)

        if len(scores) != len(candidates):
            raise ValueError("Invalid reranking scores")

        order = np.argsort(
            -np.asarray(scores, dtype=float),
            kind="stable",
        )

        return [
            candidates[i]
            for i in order[:final_k]
        ]

    def retrieve_prompt(
        self,
        question: str,
        count_tokens: Callable[[str], int],
        token_budget: int,
    ) -> str:

        if token_budget <= 0:
            return ""

        selected = []

        for chunk in self.retrieve(question):
            candidate = selected + [chunk.as_source()]
            prompt = as_prompt(candidate)

            if count_tokens(prompt) <= token_budget:
                selected = candidate

        return as_prompt(selected)