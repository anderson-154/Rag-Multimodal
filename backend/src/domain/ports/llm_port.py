# backend/src/domain/ports/llm_port.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.domain.entities.answer import Citation


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    text: str
    grounded: bool = False
    citations: list[Citation] = field(default_factory=list)


class LLMPort(ABC):
    @abstractmethod
    def chat(self, messages: list[LLMMessage]) -> LLMResponse: ...
