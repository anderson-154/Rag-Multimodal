# backend/src/domain/entities/job.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from src.domain.exceptions import InvalidJobTransitionError


class JobStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


_VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {JobStatus.PROCESSING, JobStatus.FAILED},
    JobStatus.PROCESSING: {JobStatus.PROCESSING, JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
}


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Job:
    id: str
    document_filename: str
    status: JobStatus
    progress: int = 0
    error: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def _transition_to(self, new_status: JobStatus) -> None:
        if new_status not in _VALID_TRANSITIONS[self.status]:
            raise InvalidJobTransitionError(
                f"Invalid job transition: {self.status.value} -> {new_status.value}"
            )
        self.status = new_status
        self.updated_at = _now()

    def start(self) -> None:
        self._transition_to(JobStatus.PROCESSING)

    def update_progress(self, pct: int) -> None:
        if self.status != JobStatus.PROCESSING:
            raise InvalidJobTransitionError(f"Cannot update progress in status {self.status.value}")
        if not 0 <= pct <= 100:
            raise ValueError("Progress must be between 0 and 100")
        self.progress = pct
        self.updated_at = _now()

    def complete(self) -> None:
        self._transition_to(JobStatus.COMPLETED)
        self.progress = 100
        self.error = None

    def fail(self, error: str) -> None:
        self._transition_to(JobStatus.FAILED)
        self.error = error
