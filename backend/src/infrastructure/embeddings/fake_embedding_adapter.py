# backend/src/infrastructure/embeddings/fake_embedding_adapter.py
from __future__ import annotations

import hashlib
import math
from math import ceil

from src.domain.ports.embedding_port import EmbeddingPort


class FakeEmbeddingAdapter(EmbeddingPort):
    def __init__(self, dimensions: int = 768) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectorize(text)

    def _vectorize(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw_floats: list[float] = []
        bytes_needed = self._dimensions * 4
        extended = digest * ceil(bytes_needed / len(digest))
        for i in range(self._dimensions):
            chunk = extended[i * 4 : (i + 1) * 4]
            integer = int.from_bytes(chunk, byteorder="big", signed=False)
            value = (integer / 0xFFFFFFFF) * 2.0 - 1.0
            raw_floats.append(value)

        norm_sq = sum(v * v for v in raw_floats)
        norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
        return [v / norm for v in raw_floats]
