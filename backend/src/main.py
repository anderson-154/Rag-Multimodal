from fastapi import FastAPI

from src.infrastructure.api.logging_config import setup_logging
from src.infrastructure.api.middleware import CorrelationIdMiddleware
from src.infrastructure.config.settings import get_settings

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(
    title="RAG Multimodal API",
    version=settings.version,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(CorrelationIdMiddleware)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.version,
        "env": settings.app_env.value,
    }
