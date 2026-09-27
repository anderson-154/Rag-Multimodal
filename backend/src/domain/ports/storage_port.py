# backend/src/domain/ports/storage_port.py
from __future__ import annotations

from abc import ABC, abstractmethod


class StoragePort(ABC):
    @abstractmethod
    def save_bytes(self, relative_path: str, data: bytes) -> str: ...

    @abstractmethod
    def read_bytes(self, relative_path: str) -> bytes: ...

    @abstractmethod
    def delete(self, relative_path: str) -> bool: ...

    @abstractmethod
    def full_path(self, relative_path: str) -> str: ...
