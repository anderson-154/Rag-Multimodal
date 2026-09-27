# backend/src/infrastructure/llm/openai_adapter.py
from __future__ import annotations

import logging
import time
from typing import Any, cast

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
    import openai

    _RETRYABLE_EXCS = (
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.RateLimitError,
        openai.InternalServerError,
    )
except Exception:  # pragma: no cover - openai might not be installed
    pass


class OpenAILLMAdapter(LLMPort):
    def __init__(self, api_key: str, model: str) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMUnavailableError(
                "openai package is not installed. Install it to use OpenAILLMAdapter."
            ) from exc

        self._model = model
        self._client = OpenAI(api_key=api_key)

    def chat(self, messages: list[LLMMessage]) -> LLMResponse:
        try:
            return self._chat_with_retry(messages)
        except RetryError as exc:
            raise LLMUnavailableError(
                f"OpenAI request failed after retries: {exc.last_attempt.exception()!s}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            if any(isinstance(exc, typ) for typ in _RETRYABLE_EXCS):
                raise LLMUnavailableError(f"OpenAI request failed: {exc!s}") from exc
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(_RETRYABLE_EXCS),
        reraise=True,
    )
    def _chat_with_retry(self, messages: list[LLMMessage]) -> LLMResponse:
        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=cast(
                    Any,
                    [{"role": message.role, "content": message.content} for message in messages],
                ),
                temperature=0,
            )
        except Exception as exc:
            logger.exception("OpenAI call failed during attempt")
            raise exc

        latency_ms = (time.perf_counter() - start) * 1000.0
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

        choices = getattr(response, "choices", []) or []
        if not choices:
            raise LLMUnavailableError("OpenAI returned no choices")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None) if message else None
        if content is None:
            raise LLMUnavailableError("OpenAI returned empty content")

        logger.info(
            "openai_llm_call_success",
            extra={
                "extra_data": {
                    "model": self._model,
                    "latency_ms": round(latency_ms, 2),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
            },
        )
        return LLMResponse(
            text=str(content),
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
        )
