from __future__ import annotations

from src.application.prompts.rag_prompt import (
    NO_INFO_MARKER,
    SYSTEM_PROMPT,
    build_prompt,
)
from src.application.services.rrf import reciprocal_rank_fusion
from src.domain.entities.answer import Answer, Citation, Query
from src.domain.entities.chunk import Chunk
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
        query_vector = self._embedder.embed_query(query.text)

        semantic = self._vector_store.search_semantic(
            query_vector=query_vector,
            top_k=self._top_k,
            document_ids=query.document_ids,
        )
        keyword = self._vector_store.search_keyword(
            query=query.text,
            top_k=self._top_k,
            document_ids=query.document_ids,
        )

        fused = reciprocal_rank_fusion([semantic, keyword])
        if not fused:
            return self._no_info_answer()

        ordered_chunks = [result.chunk for result in fused]
        chunks_by_id = {chunk.id: chunk for chunk in ordered_chunks}

        rerank_hits = self._rerank(query.text, ordered_chunks)
        top_chunks = [
            chunks_by_id[hit.chunk_id] for hit in rerank_hits if hit.chunk_id in chunks_by_id
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
