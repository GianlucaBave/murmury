from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .material import Source


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