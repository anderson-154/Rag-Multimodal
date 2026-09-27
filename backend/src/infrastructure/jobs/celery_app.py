# backend/src/infrastructure/jobs/celery_app.py
from __future__ import annotations

from celery import Celery

from src.infrastructure.config.settings import get_settings

settings = get_settings()

celery_app = Celery("rag_jobs")
celery_app.conf.update(
    broker_url=settings.redis_url,
    result_backend=settings.redis_url,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["src.infrastructure.jobs"], force=True)
