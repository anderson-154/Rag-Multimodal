# backend/src/infrastructure/jobs/tasks.py
from __future__ import annotations

import logging

from src.application.use_cases.ingest_document_use_case import IngestDocumentUseCase
from src.domain.entities.job import Job
from src.domain.exceptions import JobNotFoundError
from src.infrastructure.chunking.layout_aware_chunker import LayoutAwareChunker
from src.infrastructure.config.container import (
    get_embedder,
    get_vector_store,
)
from src.infrastructure.config.settings import get_settings
from src.infrastructure.jobs.celery_app import celery_app
from src.infrastructure.jobs.redis_job_repository import RedisJobRepository
from src.infrastructure.parsers.pymupdf_adapter import PyMuPDFParserAdapter

logger = logging.getLogger(__name__)


def _get_job_repository() -> RedisJobRepository:
    settings = get_settings()
    return RedisJobRepository(redis_url=settings.redis_url)


def _get_ingest_use_case() -> IngestDocumentUseCase:
    settings = get_settings()
    parser = PyMuPDFParserAdapter(
        storage_path=settings.storage_path,
        image_proximity_margin=settings.image_proximity_margin,
    )
    chunker = LayoutAwareChunker(
        max_tokens=settings.chunk_max_tokens,
        overlap=settings.chunk_overlap,
    )
    return IngestDocumentUseCase(
        parser=parser,
        chunker=chunker,
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        image_proximity_margin=settings.image_proximity_margin,
    )


@celery_app.task(bind=True, name="ingest_document_task", max_retries=0, acks_late=True)
def ingest_document_task(self, job_id: str, file_path: str, document_id: str) -> str:
    job_repo = _get_job_repository()
    use_case = _get_ingest_use_case()

    job = job_repo.get_by_id(job_id)
    if job is None:
        logger.error("ingest_job_not_found", extra={"extra_data": {"job_id": job_id}})
        raise JobNotFoundError(f"Job {job_id!r} not found")

    try:
        job.start()
        job_repo.update(job)
    except Exception as exc:  # noqa: BLE001
        logger.exception("ingest_job_start_failed", extra={"extra_data": {"job_id": job_id}})
        try:
            job.fail(str(exc))
            job_repo.update(job)
        except Exception:  # noqa: BLE001
            pass
        raise

    def progress_callback(pct: int) -> None:
        _update_progress(job_repo, job, pct)

    try:
        use_case.execute(
            file_path=file_path,
            document_id=document_id,
            on_progress=progress_callback,
        )
        job.complete()
        job_repo.update(job)
        logger.info(
            "ingest_job_completed",
            extra={"extra_data": {"job_id": job_id, "document_id": document_id}},
        )
        return job.status.value
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "ingest_job_failed",
            exc_info=True,
            extra={
                "extra_data": {
                    "job_id": job_id,
                    "document_id": document_id,
                    "file_path": file_path,
                }
            },
        )
        try:
            job.fail(str(exc))
            job_repo.update(job)
        except Exception:  # noqa: BLE001
            pass
        return job.status.value


def _update_progress(
    job_repo: RedisJobRepository,
    job: Job,
    pct: int,
) -> None:
    try:
        job.update_progress(pct)
        job_repo.update(job)
    except Exception:  # noqa: BLE001
        logger.exception(
            "ingest_job_progress_update_failed",
            extra={"extra_data": {"job_id": job.id, "progress": pct}},
        )
