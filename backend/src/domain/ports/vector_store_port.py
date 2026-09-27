# backend/src/domain/ports/vector_store_port.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.entities.chunk import Chunk


@dataclass
class SearchResult:
    chunk: Chunk
    score: float
    source: str = "semantic"


class VectorStorePort(ABC):
    @abstractmethod
    def ensure_collection(self) -> None: ...

    @abstractmethod
    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...

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
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    def delete_by_document(self, document_id: str) -> int: ...

    @abstractmethod
    def list_documents(self) -> list[str]: ...
