# backend/src/domain/ports/llm_port.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMPort(ABC):
    @abstractmethod
    def chat(self, messages: list[LLMMessage]) -> LLMResponse: ...
