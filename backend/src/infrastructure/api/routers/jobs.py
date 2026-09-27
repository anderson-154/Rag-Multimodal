# backend/src/infrastructure/api/routers/jobs.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.domain.exceptions import JobNotFoundError
from src.domain.ports.job_repository_port import JobRepositoryPort
from src.infrastructure.api.schemas import JobResponse
from src.infrastructure.config.container import get_job_repository

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    jobs: Annotated[JobRepositoryPort, Depends(get_job_repository)],
) -> JobResponse:
    job = jobs.get_by_id(job_id)
    if job is None:
        raise JobNotFoundError(job_id)
    return JobResponse(
        job_id=job.id,
        document_filename=job.document_filename,
        status=job.status,
        progress=job.progress,
        error=job.error,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
    )
