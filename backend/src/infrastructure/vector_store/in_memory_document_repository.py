# backend/src/infrastructure/vector_store/in_memory_document_repository.py
from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock

from src.domain.entities.document import Document
from src.domain.ports.document_repository_port import DocumentRepositoryPort


def _now() -> datetime:
    return datetime.now(UTC)


class InMemoryDocumentRepository(DocumentRepositoryPort):
    def __init__(self) -> None:
        self._by_id: dict[str, Document] = {}
        self._by_checksum: dict[str, str] = {}
        self._lock = RLock()

    def save(self, document: Document) -> Document:
        with self._lock:
            existing_checksum_owner = self._by_checksum.get(document.checksum)
            if existing_checksum_owner and existing_checksum_owner != document.id:
                existing = self._by_id.get(existing_checksum_owner)
                if existing is not None and existing.id != document.id:
                    return existing
            previous = self._by_id.get(document.id)
            if previous is not None and previous.checksum == document.checksum:
                return previous
            self._by_id[document.id] = document
            self._by_checksum[document.checksum] = document.id
            return document

    def get_by_id(self, document_id: str) -> Document | None:
        with self._lock:
            return self._by_id.get(document_id)

    def get_by_checksum(self, checksum: str) -> Document | None:
        with self._lock:
            doc_id = self._by_checksum.get(checksum)
            if doc_id is None:
                return None
            return self._by_id.get(doc_id)

    def list_all(self) -> list[Document]:
        with self._lock:
            return list(self._by_id.values())

    def delete(self, document_id: str) -> bool:
        with self._lock:
            document = self._by_id.pop(document_id, None)
            if document is None:
                return False
            stored_checksum = self._by_checksum.get(document.checksum)
            if stored_checksum == document_id:
                self._by_checksum.pop(document.checksum, None)
            return True
