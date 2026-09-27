# backend/src/domain/ports/vector_store_port.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    chunk_id: str
    score: float
    source: str = "semantic"


class VectorStorePort(ABC):
    @abstractmethod
    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, object]] | None = None,
    ) -> None: ...

    @abstractmethod
    def search_semantic(
        self,
        query_vector: list[float],
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    def search_keyword(
        self,
        query_text: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    def get_chunks(self, chunk_ids: list[str]) -> dict[str, dict[str, object]]: ...

    @abstractmethod
    def delete_by_document(self, document_id: str) -> int: ...
