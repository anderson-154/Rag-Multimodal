# backend/src/domain/ports/document_parser_port.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.domain.entities.bounding_box import BoundingBox


@dataclass
class ParsedBlock:
    text: str
    page: int
    bbox: BoundingBox
    block_type: str
    hierarchy_level: int = 0


@dataclass
class ParsedImage:
    page: int
    bbox: BoundingBox
    file_path: str = ""


@dataclass
class ParsedDocument:
    total_pages: int
    blocks: list[ParsedBlock] = field(default_factory=list)
    images: list[ParsedImage] = field(default_factory=list)


class DocumentParserPort(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument: ...
