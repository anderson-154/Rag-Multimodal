# backend/src/infrastructure/embeddings/openai_embedding_adapter.py
from __future__ import annotations

import logging
import time

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.exceptions import LLMUnavailableError
from src.domain.ports.embedding_port import EmbeddingPort

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100

_RETRYABLE_EXCS: tuple[type[BaseException], ...] = ()
try:
    import openai

    _RETRYABLE_EXCS = (
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.RateLimitError,
        openai.InternalServerError,
    )
except Exception:  # pragma: no cover - openai might not be installed
    pass


class OpenAIEmbeddingAdapter(EmbeddingPort):
    def __init__(self, api_key: str, model: str, dimensions: int | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMUnavailableError(
                "openai package is not installed. Install it to use OpenAIEmbeddingAdapter."
            ) from exc

        self._model = model
        self._dimensions_override = dimensions
        self._client = OpenAI(api_key=api_key)
        self._effective_dimensions: int | None = None

    @property
    def dimensions(self) -> int:
        if self._effective_dimensions is not None:
            return self._effective_dimensions
        probe = self._call_embeddings(["probe"])
        first = probe[0] if probe else []
        dims = len(first)
        self._effective_dimensions = dims
        return dims

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        batches: list[list[str]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batches.append(texts[i : i + _BATCH_SIZE])

        all_embeddings: list[list[float]] = []
        total_batches = len(batches)
        for idx, batch in enumerate(batches, start=1):
            start = time.perf_counter()
            vectors = self._call_embeddings_with_retry(batch)
            latency_ms = (time.perf_counter() - start) * 1000.0
            logger.info(
                "openai_embedding_batch",
                extra={
                    "extra_data": {
                        "model": self._model,
                        "batch_index": idx,
                        "total_batches": total_batches,
                        "batch_size": len(batch),
                        "latency_ms": round(latency_ms, 2),
                    }
                },
            )
            all_embeddings.extend(vectors)

        if self._effective_dimensions is None and all_embeddings:
            self._effective_dimensions = len(all_embeddings[0])

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        vectors = self._call_embeddings_with_retry([text])
        if not vectors:
            raise LLMUnavailableError("OpenAI embeddings returned empty vector for query")
        return vectors[0]

    def _call_embeddings_with_retry(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._call_embeddings(texts)
        except RetryError as exc:
            raise LLMUnavailableError(
                f"OpenAI embeddings failed after retries: {exc.last_attempt.exception()!s}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            if any(isinstance(exc, typ) for typ in _RETRYABLE_EXCS):
                raise LLMUnavailableError(f"OpenAI embeddings failed: {exc!s}") from exc
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(_RETRYABLE_EXCS),
        reraise=True,
    )
    def _call_embeddings(self, texts: list[str]) -> list[list[float]]:
        kwargs: dict[str, object] = {
            "model": self._model,
            "input": texts,
        }
        if self._dimensions_override is not None:
            kwargs["dimensions"] = self._dimensions_override

        response = self._client.embeddings.create(**kwargs)  # type: ignore[arg-type]
        data = getattr(response, "data", None) or []
        ordered = sorted(data, key=lambda item: getattr(item, "index", 0))
        vectors: list[list[float]] = []
        for item in ordered:
            emb = getattr(item, "embedding", None)
            if isinstance(emb, list) and all(isinstance(v, (int, float)) for v in emb):
                vectors.append([float(v) for v in emb])
            else:
                raise LLMUnavailableError("OpenAI returned malformed embedding vector")
        if len(vectors) != len(texts):
            raise LLMUnavailableError(
                f"OpenAI embeddings count mismatch: requested {len(texts)}, got {len(vectors)}"
            )
        return vectors
