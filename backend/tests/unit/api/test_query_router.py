# backend/tests/unit/api/test_query_router.py
from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from src.domain.entities.answer import Answer, Citation, Query
from src.infrastructure.config.container import get_query_use_case
from src.main import app

client = TestClient(app)


class _FakeQueryUseCase:
    def __init__(self, answer_factory: Callable[[Query], Answer] | None = None) -> None:
        self._answer_factory = answer_factory

    def execute(self, query: Query) -> Answer:
        if self._answer_factory is not None:
            return self._answer_factory(query)
        return Answer(
            text="Respuesta de ejemplo.",
            citations=[
                Citation(
                    document_name="manual.pdf",
                    page=7,
                    chunk_id="doc1-0-a1b2c3d4",
                    image_ids=["doc1_p7_0"],
                )
            ],
            is_grounded=True,
        )


def _override(fn: Callable[[], object]) -> None:
    app.dependency_overrides[get_query_use_case] = fn


def _reset_overrides() -> None:
    app.dependency_overrides.clear()


def test_query_endpoint_returns_answer_with_citations() -> None:
    fake = _FakeQueryUseCase()
    _override(lambda: fake)

    try:
        response = client.post(
            "/api/v1/query",
            json={"question": "¿Cuál es la arquitectura?", "top_k": 5},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "Respuesta de ejemplo."
        assert body["is_grounded"] is True
        assert len(body["citations"]) == 1
        citation = body["citations"][0]
        assert citation["document_name"] == "manual.pdf"
        assert citation["page"] == 7
        assert citation["chunk_id"] == "doc1-0-a1b2c3d4"
        assert citation["image_ids"] == ["doc1_p7_0"]
    finally:
        _reset_overrides()


def test_query_endpoint_passes_document_ids() -> None:
    captured: list[Query] = []

    def _factory(query: Query) -> Answer:
        captured.append(query)
        return Answer(text="ok", citations=[], is_grounded=True)

    fake = _FakeQueryUseCase(_factory)
    _override(lambda: fake)

    try:
        response = client.post(
            "/api/v1/query",
            json={
                "question": "pregunta",
                "document_ids": ["doc-a", "doc-b"],
            },
        )
        assert response.status_code == 200
        assert len(captured) == 1
        q = captured[0]
        assert q.text == "pregunta"
        assert q.document_ids == ["doc-a", "doc-b"]
    finally:
        _reset_overrides()


def test_query_endpoint_rejects_empty_question() -> None:
    fake = _FakeQueryUseCase()
    _override(lambda: fake)

    try:
        response = client.post("/api/v1/query", json={"question": ""})
        assert response.status_code == 422
    finally:
        _reset_overrides()


def test_query_endpoint_returns_correlation_id_header() -> None:
    fake = _FakeQueryUseCase()
    _override(lambda: fake)

    try:
        response = client.post("/api/v1/query", json={"question": "hola"})
        assert response.headers.get("X-Correlation-ID")
    finally:
        _reset_overrides()
