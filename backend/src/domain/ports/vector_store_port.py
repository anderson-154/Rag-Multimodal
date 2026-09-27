# backend/src/domain/ports/vector_store_port.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VectorSearchHit:
    chunk_id: str
    score: float


class VectorStorePort(ABC):
    @abstractmethod
    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, object]] | None = None,
    ) -> None: ...

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[VectorSearchHit]: ...

    @abstractmethod
    def delete_by_document(self, document_id: str) -> int: ...
