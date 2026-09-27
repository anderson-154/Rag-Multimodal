# backend/src/domain/entities/document.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.entities.bounding_box import BoundingBox


@dataclass
class ExtractedImage:
    id: str
    file_path: str
    page: int
    bbox: BoundingBox
    caption: str | None = None


@dataclass
class Document:
    id: str
    filename: str
    checksum: str
    total_pages: int
    ingested_at: datetime
