# backend/tests/unit/application/fakes.py
from __future__ import annotations

from src.domain.entities.chunk import Chunk
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.llm_port import LLMMessage, LLMPort, LLMResponse
from src.domain.ports.reranker_port import RerankerPort, RerankHit
from src.domain.ports.vector_store_port import SearchResult, VectorStorePort


class FakeEmbedder(EmbeddingPort):
    def __init__(self, dimensions: int = 8) -> None:
        self._dimensions = dimensions
        self.called_documents: list[list[str]] = []
        self.called_queries: list[str] = []

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.called_documents.append(list(texts))
        return [[float(i + 1)] * self._dimensions for i in range(len(texts))]

    def embed_query(self, text: str) -> list[float]:
        self.called_queries.append(text)
        return [1.0] * self._dimensions


class FakeVectorStore(VectorStorePort):
    def __init__(
        self,
        semantic_results: list[SearchResult] | None = None,
        keyword_results: list[SearchResult] | None = None,
    ) -> None:
        self.semantic_results = list(semantic_results or [])
        self.keyword_results = list(keyword_results or [])
        self.upsert_calls: list[dict[str, object]] = []
        self.semantic_calls: list[dict[str, object]] = []
        self.keyword_calls: list[dict[str, object]] = []

    def ensure_collection(self) -> None:
        pass

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        self.upsert_calls.append({"chunks": chunks, "vectors": vectors})

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
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        self.keyword_calls.append({"query": query, "top_k": top_k, "document_ids": document_ids})
        return list(self.keyword_results)

    def delete_by_document(self, document_id: str) -> int:
        return 0

    def list_documents(self) -> list[str]:
        return []


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
        self.call_log: list[list[LLMMessage]] = []

    def chat(self, messages: list[LLMMessage]) -> LLMResponse:
        self.call_log.append(list(messages))
        return LLMResponse(text=self.response_text)
