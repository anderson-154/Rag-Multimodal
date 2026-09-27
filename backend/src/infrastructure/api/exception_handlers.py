# backend/src/infrastructure/api/exception_handlers.py
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.domain import exceptions as domain_exceptions
from src.infrastructure.api.logging_config import CORRELATION_ID

logger = logging.getLogger(__name__)

_ERROR_CODE_MAP: dict[type[domain_exceptions.DomainError], tuple[int, str]] = {
    domain_exceptions.DocumentNotFoundError: (status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND"),
    domain_exceptions.JobNotFoundError: (status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND"),
    domain_exceptions.UnsupportedFileTypeError: (
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        "UNSUPPORTED_FILE_TYPE",
    ),
    domain_exceptions.LLMUnavailableError: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "LLM_UNAVAILABLE",
    ),
    domain_exceptions.VectorStoreError: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "VECTOR_STORE_ERROR",
    ),
    domain_exceptions.InvalidJobTransitionError: (
        status.HTTP_400_BAD_REQUEST,
        "INVALID_JOB_TRANSITION",
    ),
}


def _error_body(exc: Exception, http_status: int, error_code: str) -> dict[str, Any]:
    return {
        "detail": str(exc) or error_code.replace("_", " ").title(),
        "error_code": error_code,
        "correlation_id": CORRELATION_ID.get(),
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(domain_exceptions.DomainError)
    async def _domain_error_handler(
        request: Request, exc: domain_exceptions.DomainError
    ) -> JSONResponse:
        mapping = _ERROR_CODE_MAP.get(type(exc))
        if mapping is None:
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_code = "DOMAIN_ERROR"
        else:
            http_status, error_code = mapping
        if http_status >= 500:
            logger.exception(
                "domain_error",
                exc_info=exc,
                extra={
                    "extra_data": {
                        "error_code": error_code,
                        "path": request.url.path,
                        "method": request.method,
                    }
                },
            )
        else:
            logger.warning(
                "domain_error",
                exc_info=exc,
                extra={
                    "extra_data": {
                        "error_code": error_code,
                        "path": request.url.path,
                        "method": request.method,
                    }
                },
            )
        return JSONResponse(
            status_code=http_status,
            content=_error_body(exc, http_status, error_code),
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_error",
            exc_info=exc,
            extra={
                "extra_data": {
                    "path": request.url.path,
                    "method": request.method,
                }
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                exc,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "INTERNAL_SERVER_ERROR",
            ),
        )
