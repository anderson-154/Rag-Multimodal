# backend/src/domain/ports/chunk_repository_port.py
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.chunk import Chunk


class ChunkRepositoryPort(ABC):
    @abstractmethod
    def save_many(self, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    def get_by_id(self, chunk_id: str) -> Chunk | None: ...

    @abstractmethod
    def get_by_document(self, document_id: str) -> list[Chunk]: ...

    @abstractmethod
    def delete_by_document(self, document_id: str) -> int: ...
