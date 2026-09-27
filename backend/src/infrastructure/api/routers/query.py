# backend/src/infrastructure/api/routers/query.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.application.use_cases.query_use_case import QueryUseCase
from src.domain.entities.answer import Answer, Citation, Query
from src.infrastructure.api.schemas import (
    CitationResponse,
    QueryRequest,
    QueryResponse,
)
from src.infrastructure.config.container import get_query_use_case
from src.infrastructure.config.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def query_documents(
    payload: QueryRequest,
    use_case: Annotated[QueryUseCase, Depends(get_query_use_case)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QueryResponse:
    query = Query(
        text=payload.question,
        top_k=payload.top_k or settings.top_k_retrieval,
        document_ids=payload.document_ids,
    )
    answer: Answer = use_case.execute(query)
    return _map_answer(answer)


def _map_citation(citation: Citation) -> CitationResponse:
    return CitationResponse(
        document_name=citation.document_name,
        page=citation.page,
        chunk_id=citation.chunk_id,
        image_ids=list(citation.image_ids),
    )


def _map_answer(answer: Answer) -> QueryResponse:
    return QueryResponse(
        answer=answer.text,
        citations=[_map_citation(c) for c in answer.citations],
        is_grounded=answer.is_grounded,
    )
