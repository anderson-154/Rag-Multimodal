# backend/src/domain/ports/chunker_port.py
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.chunk import Chunk
from src.domain.ports.document_parser_port import ParsedDocument


class ChunkerPort(ABC):
    @abstractmethod
    def chunk(
        self,
        document_id: str,
        parsed: ParsedDocument,
    ) -> list[Chunk]: ...
