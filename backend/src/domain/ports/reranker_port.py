# backend/src/domain/ports/reranker_port.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RerankHit:
    chunk_id: str
    score: float


class RerankerPort(ABC):
    @abstractmethod
    def rerank(
        self,
        query: str,
        chunk_ids: list[str],
        chunk_texts: list[str],
        top_n: int,
    ) -> list[RerankHit]: ...
