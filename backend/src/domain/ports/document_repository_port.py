# backend/src/domain/ports/document_repository_port.py
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.document import Document


class DocumentRepositoryPort(ABC):
    @abstractmethod
    def save(self, document: Document) -> Document: ...

    @abstractmethod
    def get_by_id(self, document_id: str) -> Document | None: ...

    @abstractmethod
    def get_by_checksum(self, checksum: str) -> Document | None: ...

    @abstractmethod
    def list_all(self) -> list[Document]: ...

    @abstractmethod
    def delete(self, document_id: str) -> bool: ...
