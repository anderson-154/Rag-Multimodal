# backend/tests/unit/application/fakes.py
from __future__ import annotations

from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.llm_port import LLMMessage, LLMPort, LLMResponse
from src.domain.ports.reranker_port import RerankerPort, RerankHit
from src.domain.ports.vector_store_port import SearchResult, VectorStorePort


class FakeEmbedder(EmbeddingPort):
    def __init__(self, dimensions: int = 8) -> None:
        self._dimensions = dimensions
        self.called_texts: list[list[str]] = []

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.called_texts.append(list(texts))
        return [[float(i + 1)] * self._dimensions for i in range(len(texts))]


class FakeVectorStore(VectorStorePort):
    def __init__(
        self,
        semantic_results: list[SearchResult] | None = None,
        keyword_results: list[SearchResult] | None = None,
        chunks_data: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.semantic_results = list(semantic_results or [])
        self.keyword_results = list(keyword_results or [])
        self.chunks_data = dict(chunks_data or {})
        self.upsert_calls: list[object] = []
        self.semantic_calls: list[dict[str, object]] = []
        self.keyword_calls: list[dict[str, object]] = []

    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, object]] | None = None,
    ) -> None:
        self.upsert_calls.append({"ids": ids, "vectors": vectors, "payloads": payloads})

    def search_semantic(
        self,
        query_vector: list[float],
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        self.semantic_calls.append(
            {"query_vector": query_vector, "top_k": top_k, "document_ids": document_ids}
        )
        return list(self.semantic_results)

    def search_keyword(
        self,
        query_text: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        self.keyword_calls.append(
            {"query_text": query_text, "top_k": top_k, "document_ids": document_ids}
        )
        return list(self.keyword_results)

    def get_chunks(self, chunk_ids: list[str]) -> dict[str, dict[str, object]]:
        return {cid: self.chunks_data[cid] for cid in chunk_ids if cid in self.chunks_data}

    def delete_by_document(self, document_id: str) -> int:
        return 0


class FakeReranker(RerankerPort):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def rerank(
        self,
        query: str,
        chunk_ids: list[str],
        chunk_texts: list[str],
        top_n: int,
    ) -> list[RerankHit]:
        self.calls.append({"query": query, "chunk_ids": list(chunk_ids), "top_n": top_n})
        hits = [
            RerankHit(chunk_id=cid, score=float(len(chunk_ids) - i))
            for i, cid in enumerate(chunk_ids)
        ]
        return hits[:top_n]


class FakeLLM(LLMPort):
    def __init__(self, response_text: str = "Respuesta de prueba.") -> None:
        self.response_text = response_text
        self.message_logs: list[list[LLMMessage]] = []

    def chat(self, messages: list[LLMMessage]) -> LLMResponse:
        self.message_logs.append([LLMMessage(m.role, m.content) for m in messages])
        return LLMResponse(text=self.response_text)
