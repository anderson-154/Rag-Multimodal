from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.infrastructure.api.exception_handlers import register_exception_handlers
from src.infrastructure.api.logging_config import setup_logging
from src.infrastructure.api.middleware import CorrelationIdMiddleware
from src.infrastructure.api.routers.documents import documents_router, images_router
from src.infrastructure.api.routers.jobs import router as jobs_router
from src.infrastructure.api.routers.query import router as query_router
from src.infrastructure.config.settings import AppEnv, get_settings

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(
    title="RAG Multimodal API",
    version=settings.version,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

if settings.app_env in {AppEnv.DEVELOPMENT, AppEnv.TESTING}:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(CorrelationIdMiddleware)

register_exception_handlers(app)

app.include_router(documents_router)
app.include_router(images_router)
app.include_router(jobs_router)
app.include_router(query_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.version,
        "env": settings.app_env.value,
    }
