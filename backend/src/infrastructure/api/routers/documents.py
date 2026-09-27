# backend/src/infrastructure/api/routers/documents.py
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from src.domain.entities.document import Document
from src.domain.entities.job import Job, JobStatus
from src.domain.exceptions import DocumentNotFoundError, UnsupportedFileTypeError
from src.domain.ports.document_repository_port import DocumentRepositoryPort
from src.domain.ports.job_repository_port import JobRepositoryPort
from src.infrastructure.api.schemas import DocumentResponse, UploadResponse
from src.infrastructure.config.container import (
    get_document_repository,
    get_job_repository,
    get_vector_store,
)
from src.infrastructure.config.settings import Settings, get_settings
from src.infrastructure.jobs.tasks import ingest_document_task

documents_router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
images_router = APIRouter(prefix="/api/v1/images", tags=["images"])
logger = logging.getLogger(__name__)

_ALLOWED_EXT = {".pdf"}
_READ_CHUNK = 64 * 1024


def _now() -> datetime:
    return datetime.now(UTC)


@documents_router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=UploadResponse)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    settings: Annotated[Settings, Depends(get_settings)],
    documents: Annotated[DocumentRepositoryPort, Depends(get_document_repository)],
    jobs: Annotated[JobRepositoryPort, Depends(get_job_repository)],
) -> UploadResponse:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Missing filename")
    filename = Path(file.filename).name
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise UnsupportedFileTypeError(f"Unsupported file type: {ext}")

    storage_root = Path(settings.storage_path).resolve()
    storage_root.mkdir(parents=True, exist_ok=True)
    (storage_root / "uploads").mkdir(parents=True, exist_ok=True)
    (storage_root / "images").mkdir(parents=True, exist_ok=True)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    checksum, _file_size, stored_path = await _stream_and_store(
        upload=file, storage_root=storage_root, max_bytes=max_bytes
    )

    existing = documents.get_by_checksum(checksum)
    if existing is not None:
        try:
            os.remove(stored_path)
        except OSError:
            pass
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        job = Job(
            id=job_id,
            document_filename=existing.filename,
            status=JobStatus.COMPLETED,
            progress=100,
            error=None,
            created_at=_now(),
            updated_at=_now(),
        )
        jobs.save(job)
        return UploadResponse(
            job_id=job_id,
            filename=existing.filename,
            status=job.status,
            document_id=existing.id,
            checksum=checksum,
            already_existed=True,
        )

    document_id = f"{Path(filename).stem}-{uuid.uuid4().hex[:8]}"
    document = Document(
        id=document_id,
        filename=filename,
        checksum=checksum,
        total_pages=0,
        ingested_at=_now(),
    )
    documents.save(document)

    job_id = f"job-{uuid.uuid4().hex[:8]}"
    job = Job(
        id=job_id,
        document_filename=filename,
        status=JobStatus.PENDING,
        progress=0,
        error=None,
        created_at=_now(),
        updated_at=_now(),
    )
    jobs.save(job)

    try:
        ingest_document_task.delay(job_id, str(stored_path), document_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "enqueue_ingest_failed",
            extra={"extra_data": {"job_id": job_id, "document_id": document_id}},
        )
        job.fail(str(exc))
        jobs.update(job)
        raise HTTPException(
            status_code=503,
            detail="Failed to enqueue ingest task. Try again later.",
        ) from exc

    return UploadResponse(
        job_id=job_id,
        filename=filename,
        status=job.status,
        document_id=document_id,
        checksum=checksum,
        already_existed=False,
    )


@documents_router.get("", response_model=list[DocumentResponse])
def list_documents(
    documents: Annotated[DocumentRepositoryPort, Depends(get_document_repository)],
) -> list[DocumentResponse]:
    items = documents.list_all()
    return [
        DocumentResponse(
            id=document.id,
            filename=document.filename,
            checksum=document.checksum,
            total_pages=document.total_pages,
            ingested_at=document.ingested_at.isoformat(),
            images=0,
        )
        for document in items
    ]


@documents_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    documents: Annotated[DocumentRepositoryPort, Depends(get_document_repository)],
    vector_store: Annotated[object, Depends(get_vector_store)],
) -> None:
    existing = documents.get_by_id(document_id)
    if existing is None:
        raise DocumentNotFoundError(document_id)
    documents.delete(document_id)
    delete_fn = getattr(vector_store, "delete_by_document", None)
    if callable(delete_fn):
        try:
            delete_fn(document_id)
        except Exception:  # noqa: BLE001
            logger.exception(
                "delete_vector_doc_failed",
                extra={"extra_data": {"document_id": document_id}},
            )


@images_router.get("/{image_id}")
def get_image(
    image_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    if not image_id or "/" in image_id or "\\" in image_id or ".." in image_id:
        raise HTTPException(status_code=400, detail="Invalid image id")

    storage_root = Path(settings.storage_path).resolve()
    candidate = (storage_root / "images" / f"{image_id}.png").resolve()

    try:
        candidate.relative_to(storage_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid image path") from exc

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(
        path=str(candidate),
        media_type="image/png",
        filename=candidate.name,
    )


async def _stream_and_store(
    upload: UploadFile,
    storage_root: Path,
    max_bytes: int,
) -> tuple[str, int, Path]:
    hasher = hashlib.sha256()
    safe_name = f"{uuid.uuid4().hex}.pdf"
    target = (storage_root / "uploads" / safe_name).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.relative_to(storage_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid storage path") from exc

    total = 0
    with open(target, "wb") as fh:
        while True:
            chunk = await upload.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                try:
                    os.remove(target)
                except OSError:
                    pass
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum allowed size is {max_bytes // (1024 * 1024)} MB.",
                )
            hasher.update(chunk)
            fh.write(chunk)

    return hasher.hexdigest(), total, target
