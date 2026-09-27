# backend/src/infrastructure/vector_store/in_memory_adapter.py
from __future__ import annotations

import math

from src.domain.entities.chunk import Chunk
from src.domain.ports.vector_store_port import SearchResult, VectorStorePort


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStoreAdapter(VectorStorePort):
    def __init__(self) -> None:
        self._vectors_by_chunk: dict[str, list[float]] = {}
        self._chunks_by_id: dict[str, Chunk] = {}

    def ensure_collection(self) -> None:
        return None

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._chunks_by_id[chunk.id] = chunk
            self._vectors_by_chunk[chunk.id] = list(vector)

    def search_semantic(
        self,
        query_vector: list[float],
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        allowed = set(document_ids) if document_ids else None
        scored: list[tuple[float, Chunk]] = []
        for cid, vector in self._vectors_by_chunk.items():
            chunk = self._chunks_by_id[cid]
            if allowed is not None and chunk.document_id not in allowed:
                continue
            score = _cosine_similarity(query_vector, vector)
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            SearchResult(chunk=chunk, score=score, source="semantic")
            for score, chunk in scored[:top_k]
        ]

    def search_keyword(
        self,
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        if not query:
            return []
        needle = query.lower()
        allowed = set(document_ids) if document_ids else None
        scored: list[tuple[float, Chunk]] = []
        for chunk in self._chunks_by_id.values():
            if allowed is not None and chunk.document_id not in allowed:
                continue
            haystack = f"{chunk.hierarchy_path} {chunk.content}".lower()
            if needle not in haystack:
                continue
            count = haystack.count(needle)
            score = float(count)
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            SearchResult(chunk=chunk, score=score, source="keyword")
            for score, chunk in scored[:top_k]
        ]

    def delete_by_document(self, document_id: str) -> int:
        deleted_ids = [
            cid for cid, chunk in self._chunks_by_id.items() if chunk.document_id == document_id
        ]
        for cid in deleted_ids:
            self._chunks_by_id.pop(cid, None)
            self._vectors_by_chunk.pop(cid, None)
        return len(deleted_ids)

    def list_documents(self) -> list[str]:
        return sorted({chunk.document_id for chunk in self._chunks_by_id.values()})
