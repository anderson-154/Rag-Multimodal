# backend/src/domain/ports/job_repository_port.py
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.job import Job


class JobRepositoryPort(ABC):
    @abstractmethod
    def save(self, job: Job) -> Job: ...

    @abstractmethod
    def get_by_id(self, job_id: str) -> Job | None: ...

    @abstractmethod
    def list_all(self) -> list[Job]: ...

    @abstractmethod
    def update(self, job: Job) -> Job: ...
