# backend/src/infrastructure/api/schemas.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.domain.entities.job import JobStatus


class QueryRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "question": "¿Cuáles son los componentes principales de la arquitectura?",
                "top_k": 10,
                "document_ids": ["manual_tecnico_v2.pdf-abc123"],
            }
        },
    )

    question: str = Field(..., min_length=1, max_length=10_000)
    top_k: int | None = Field(default=None, ge=1, le=100)
    document_ids: list[str] | None = Field(default=None, min_length=1)


class CitationResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_name": "manual.pdf",
                "page": 7,
                "chunk_id": "doc1-0-a1b2c3d4",
                "image_ids": ["doc1_p7_0"],
            }
        }
    )

    document_name: str
    page: int
    chunk_id: str
    image_ids: list[str] = []


class QueryResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "La arquitectura tiene tres capas principales [manual.pdf, p.7].",
                "citations": [
                    {
                        "document_name": "manual.pdf",
                        "page": 7,
                        "chunk_id": "doc1-0-a1b2c3d4",
                        "image_ids": ["doc1_p7_0"],
                    }
                ],
                "is_grounded": True,
            }
        }
    )

    answer: str
    citations: list[CitationResponse] = []
    is_grounded: bool


class UploadResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "job-abc123",
                "filename": "manual.pdf",
                "status": "PENDING",
                "document_id": "doc1",
                "checksum": "sha256-abc",
            }
        }
    )

    job_id: str
    filename: str
    status: str | JobStatus
    document_id: str
    checksum: str
    already_existed: bool = False


class JobResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "job-abc123",
                "document_filename": "manual.pdf",
                "status": "PROCESSING",
                "progress": 60,
                "error": None,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:01:00Z",
            }
        }
    )

    job_id: str
    document_filename: str
    status: JobStatus
    progress: int
    error: str | None = None
    created_at: str
    updated_at: str


class DocumentResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "doc1",
                "filename": "manual.pdf",
                "checksum": "sha256-abc",
                "total_pages": 42,
                "ingested_at": "2026-01-01T00:00:00Z",
                "images": 5,
            }
        }
    )

    id: str
    filename: str
    checksum: str
    total_pages: int
    ingested_at: str
    images: int = 0
