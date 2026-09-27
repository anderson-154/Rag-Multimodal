# backend/src/domain/entities/chunk.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from src.domain.entities.bounding_box import BoundingBox


class ChunkType(StrEnum):
    TEXT = "TEXT"
    TABLE = "TABLE"
    TITLE = "TITLE"
    CAPTION = "CAPTION"


@dataclass
class Chunk:
    id: str
    content: str
    hierarchy_path: str
    document_id: str
    page: int
    bbox: BoundingBox
    chunk_type: ChunkType
    parent_id: str | None = None
    image_ids: list[str] = field(default_factory=list)

    @property
    def embedding_text(self) -> str:
        return f"{self.hierarchy_path}\n{self.content}"
