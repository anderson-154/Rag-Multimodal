# backend/src/infrastructure/llm/ollama_adapter.py
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
from src.domain.ports.llm_port import LLMMessage, LLMPort, LLMResponse

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


def _split_messages(messages: list[LLMMessage]) -> tuple[str, str]:
    system_parts = [m.content for m in messages if m.role == "system"]
    user_parts = [m.content for m in messages if m.role != "system"]
    return "\n".join(system_parts), "\n".join(user_parts)


class OllamaLLMAdapter(LLMPort):
    def __init__(self, base_url: str, model: str, timeout_s: float = 120.0) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise LLMUnavailableError(
                "httpx package is not installed. Install it to use OllamaLLMAdapter."
            ) from exc

        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_s
        self._client = httpx.Client(timeout=timeout_s)

    def chat(self, messages: list[LLMMessage]) -> LLMResponse:
        try:
            return self._chat_with_retry(messages)
        except RetryError as exc:
            raise LLMUnavailableError(
                f"Ollama request failed after retries: {exc.last_attempt.exception()!s}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            if any(isinstance(exc, typ) for typ in _RETRYABLE_EXCS):
                raise LLMUnavailableError(f"Ollama request failed: {exc!s}") from exc
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(_RETRYABLE_EXCS),
        reraise=True,
    )
    def _chat_with_retry(self, messages: list[LLMMessage]) -> LLMResponse:
        import httpx

        system_prompt, prompt = _split_messages(messages)

        start = time.perf_counter()
        url = f"{self._base_url}/api/generate"
        payload: dict[str, object] = {
            "model": self._model,
            "system": system_prompt,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            response = self._client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "ollama_http_error",
                extra={
                    "extra_data": {
                        "status_code": exc.response.status_code,
                        "url": url,
                        "model": self._model,
                    }
                },
            )
            if exc.response.status_code == 429 or exc.response.status_code >= 500:
                raise
            raise LLMUnavailableError(
                f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:500]}"
            ) from exc
        except Exception as exc:
            logger.exception("Ollama call failed during attempt")
            raise exc

        latency_ms = (time.perf_counter() - start) * 1000.0
        response_text = data.get("response") if isinstance(data, dict) else None
        eval_count = data.get("eval_count") if isinstance(data, dict) else None
        prompt_eval_count = data.get("prompt_eval_count") if isinstance(data, dict) else None

        if not isinstance(response_text, str):
            raise LLMUnavailableError("Ollama returned empty or invalid response")

        logger.info(
            "ollama_llm_call_success",
            extra={
                "extra_data": {
                    "model": self._model,
                    "base_url": self._base_url,
                    "latency_ms": round(latency_ms, 2),
                    "prompt_eval_count": prompt_eval_count,
                    "eval_count": eval_count,
                }
            },
        )
        return LLMResponse(
            text=response_text,
            input_tokens=prompt_eval_count,
            output_tokens=eval_count,
        )
