# backend/src/domain/ports/embedding_port.py
from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingPort(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    @abstractmethod
    def dimensions(self) -> int: ...
