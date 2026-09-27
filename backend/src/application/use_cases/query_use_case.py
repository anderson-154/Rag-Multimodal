from __future__ import annotations

from src.application.prompts.rag_prompt import (
    NO_INFO_MARKER,
    SYSTEM_PROMPT,
    build_prompt,
)
from src.application.services.rrf import reciprocal_rank_fusion
from src.domain.entities.answer import Answer, Citation, Query
from src.domain.entities.bounding_box import BoundingBox
from src.domain.entities.chunk import Chunk, ChunkType
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.llm_port import LLMMessage, LLMPort
from src.domain.ports.reranker_port import RerankerPort, RerankHit
from src.domain.ports.vector_store_port import VectorStorePort


class QueryUseCase:
    """Orchestrates the RAG retrieval and generation flow."""

    def __init__(
        self,
        embedder: EmbeddingPort,
        vector_store: VectorStorePort,
        reranker: RerankerPort,
        llm: LLMPort,
        top_k: int,
        top_n: int,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._reranker = reranker
        self._llm = llm
        self._top_k = top_k
        self._top_n = top_n

    def execute(self, query: Query) -> Answer:
        query_vector = self._embedder.embed([query.text])[0]

        semantic = self._vector_store.search_semantic(
            query_vector=query_vector,
            top_k=self._top_k,
            document_ids=query.document_ids,
        )
        keyword = self._vector_store.search_keyword(
            query_text=query.text,
            top_k=self._top_k,
            document_ids=query.document_ids,
        )

        fused = reciprocal_rank_fusion([semantic, keyword])
        if not fused:
            return self._no_info_answer()

        fused_ids = [hit.chunk_id for hit in fused]
        id_to_chunk = self._materialize_chunks(self._vector_store.get_chunks(fused_ids))
        chunks_in_order = [id_to_chunk[cid] for cid in fused_ids if cid in id_to_chunk]

        if not chunks_in_order:
            return self._no_info_answer()

        rerank_hits = self._rerank(query.text, chunks_in_order)
        top_chunks = [
            id_to_chunk[hit.chunk_id] for hit in rerank_hits if hit.chunk_id in id_to_chunk
        ]

        if not top_chunks:
            return self._no_info_answer()

        llm_response = self._llm.chat(
            messages=[
                LLMMessage(role="system", content=SYSTEM_PROMPT),
                LLMMessage(role="user", content=build_prompt(query.text, top_chunks)),
            ]
        )

        return Answer(
            text=llm_response.text,
            citations=self._build_citations(top_chunks),
            is_grounded=NO_INFO_MARKER not in llm_response.text,
        )

    def _no_info_answer(self) -> Answer:
        return Answer(text=NO_INFO_MARKER, citations=[], is_grounded=False)

    def _materialize_chunks(self, payloads: dict[str, dict[str, object]]) -> dict[str, Chunk]:
        """Rebuilds domain Chunks from vector store payloads, skipping malformed ones."""
        materialized: dict[str, Chunk] = {}

        for chunk_id, payload in payloads.items():
            bbox = payload.get("bbox")
            chunk_type = payload.get("chunk_type")

            if not isinstance(bbox, BoundingBox) or not isinstance(chunk_type, str):
                continue

            parent_id = payload.get("parent_id")
            raw_image_ids = payload.get("image_ids") or []
            if not isinstance(raw_image_ids, list):
                raw_image_ids = []
            image_ids = [str(image_id) for image_id in raw_image_ids]

            materialized[chunk_id] = Chunk(
                id=chunk_id,
                content=str(payload.get("content", "")),
                hierarchy_path=str(payload.get("hierarchy_path", "")),
                document_id=str(payload.get("document_id", "")),
                page=int(str(payload.get("page", 0))),
                bbox=bbox,
                chunk_type=ChunkType(chunk_type),
                parent_id=str(parent_id) if parent_id is not None else None,
                image_ids=image_ids,
            )

        return materialized

    def _rerank(self, query_text: str, chunks: list[Chunk]) -> list[RerankHit]:
        return self._reranker.rerank(
            query=query_text,
            chunk_ids=[chunk.id for chunk in chunks],
            chunk_texts=[chunk.embedding_text for chunk in chunks],
            top_n=self._top_n,
        )

    def _build_citations(self, chunks: list[Chunk]) -> list[Citation]:
        """Groups chunks by document and page, merging every associated image."""
        first_chunk_id: dict[tuple[str, int], str] = {}
        merged_images: dict[tuple[str, int], list[str]] = {}
        order: list[tuple[str, int]] = []

        for chunk in chunks:
            key = (chunk.document_id, chunk.page)

            if key not in merged_images:
                merged_images[key] = []
                first_chunk_id[key] = chunk.id
                order.append(key)

            for image_id in chunk.image_ids:
                if image_id not in merged_images[key]:
                    merged_images[key].append(image_id)

        return [
            Citation(
                document_name=document_name,
                page=page,
                chunk_id=first_chunk_id[(document_name, page)],
                image_ids=merged_images[(document_name, page)],
            )
            for document_name, page in order
        ]
