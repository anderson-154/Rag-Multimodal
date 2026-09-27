# backend/src/infrastructure/jobs/redis_job_repository.py
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from src.domain.entities.job import Job, JobStatus
from src.domain.ports.job_repository_port import JobRepositoryPort

_JOB_KEY_PREFIX = "job:"
_ALL_JOBS_SET_KEY = "jobs:all"
_TTL = timedelta(hours=24)


class RedisJobRepository(JobRepositoryPort):
    def __init__(self, redis_url: str) -> None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError(
                "redis package is not installed. Install it to use RedisJobRepository."
            ) from exc
        self._redis_url = redis_url
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def save(self, job: Job) -> Job:
        return self._persist(job)

    def update(self, job: Job) -> Job:
        return self._persist(job)

    def get_by_id(self, job_id: str) -> Job | None:
        raw = self._redis.get(_JOB_KEY_PREFIX + job_id)
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return self._from_dict(payload)

    def list_all(self) -> list[Job]:
        raw_ids = self._redis.smembers(_ALL_JOBS_SET_KEY) or set()
        ids = [item.decode("utf-8") if isinstance(item, bytes) else str(item) for item in raw_ids]
        jobs: list[Job] = []
        if not ids:
            return jobs
        keys = [_JOB_KEY_PREFIX + job_id for job_id in ids]
        values = self._redis.mget(keys)
        for raw in values:
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except (ValueError, TypeError):
                continue
            job = self._from_dict(payload)
            if job is not None:
                jobs.append(job)
        return jobs

    def _persist(self, job: Job) -> Job:
        key = _JOB_KEY_PREFIX + job.id
        payload = self._to_dict(job)
        encoded = json.dumps(payload, ensure_ascii=False, default=str)
        pipe = self._redis.pipeline()
        pipe.set(key, encoded, ex=_TTL)
        pipe.sadd(_ALL_JOBS_SET_KEY, job.id)
        pipe.execute()
        return job

    def _to_dict(self, job: Job) -> dict[str, object]:
        return {
            "id": job.id,
            "document_filename": job.document_filename,
            "status": job.status.value,
            "progress": job.progress,
            "error": job.error,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }

    def _from_dict(self, data: dict[str, object]) -> Job:
        return Job(
            id=str(data["id"]),
            document_filename=str(data.get("document_filename", "")),
            status=JobStatus(str(data["status"])),
            progress=self._parse_progress(data.get("progress", 0)),
            error=str(data["error"]) if data.get("error") is not None else None,
            created_at=self._parse_dt(data.get("created_at")),
            updated_at=self._parse_dt(data.get("updated_at")),
        )

    @staticmethod
    def _parse_progress(value: object) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float, str)):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0

    @staticmethod
    def _parse_dt(value: object) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
            except ValueError:
                dt = datetime.now(UTC)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        return datetime.now(UTC)
