# backend/src/domain/entities/answer.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Citation:
    document_name: str
    page: int
    chunk_id: str
    image_ids: list[str] = field(default_factory=list)


@dataclass
class Answer:
    text: str
    citations: list[Citation] = field(default_factory=list)
    is_grounded: bool = False


@dataclass
class Query:
    text: str
    top_k: int
    document_ids: list[str] | None = None
