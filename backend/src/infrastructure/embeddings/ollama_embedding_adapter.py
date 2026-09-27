# backend/src/infrastructure/embeddings/ollama_embedding_adapter.py
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

_RETRYABLE_EXCS: tuple[type[BaseException], ...] = ()
try:
    import httpx

    _RETRYABLE_EXCS = (
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
        httpx.RemoteProtocolError,
        httpx.HTTPStatusError,
    )
except Exception:  # pragma: no cover - httpx might not be installed
    pass


class OllamaEmbeddingAdapter(EmbeddingPort):
    """Embedding adapter backed by a local Ollama server.

    Ollama's /api/embeddings endpoint accepts a single prompt per call, so
    batching here is implemented as sequential requests rather than a single
    batched HTTP call (unlike the OpenAI adapter, which supports true batch
    embedding in one request).
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        dimensions: int,
        timeout_s: float = 120.0,
    ) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise LLMUnavailableError(
                "httpx package is not installed. Install it to use OllamaEmbeddingAdapter."
            ) from exc

        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimensions = dimensions
        self._timeout = timeout_s
        self._client = httpx.Client(timeout=timeout_s)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        try:
            return self._embed_with_retry(text)
        except RetryError as exc:
            raise LLMUnavailableError(
                f"Ollama embeddings request failed after retries: {exc.last_attempt.exception()!s}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            if any(isinstance(exc, typ) for typ in _RETRYABLE_EXCS):
                raise LLMUnavailableError(f"Ollama embeddings request failed: {exc!s}") from exc
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(_RETRYABLE_EXCS),
        reraise=True,
    )
    def _embed_with_retry(self, text: str) -> list[float]:
        start = time.perf_counter()
        url = f"{self._base_url}/api/embeddings"
        payload = {"model": self._model, "prompt": text}

        try:
            response = self._client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.exception("Ollama embeddings call failed during attempt")
            raise exc

        embedding = data.get("embedding") if isinstance(data, dict) else None
        if not isinstance(embedding, list) or not embedding:
            raise LLMUnavailableError("Ollama returned empty or invalid embedding")

        latency_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "ollama_embedding_call_success",
            extra={
                "extra_data": {
                    "model": self._model,
                    "latency_ms": round(latency_ms, 2),
                    "dimensions": len(embedding),
                }
            },
        )
        return [float(v) for v in embedding]
