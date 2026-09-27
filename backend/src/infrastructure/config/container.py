# backend/src/infrastructure/config/container.py
from __future__ import annotations

import logging
from functools import lru_cache

from src.application.use_cases.query_use_case import QueryUseCase
from src.domain.exceptions import LLMUnavailableError, VectorStoreError
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.llm_port import LLMPort
from src.domain.ports.reranker_port import RerankerPort
from src.domain.ports.vector_store_port import VectorStorePort
from src.infrastructure.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_llm() -> LLMPort:
    settings: Settings = get_settings()
    provider = settings.llm_provider.strip().lower()
    if provider == "openai":
        from src.infrastructure.llm.openai_adapter import OpenAILLMAdapter

        api_key = settings.openai_api_key
        if not api_key:
            raise LLMUnavailableError("LLM_PROVIDER=openai requires OPENAI_API_KEY to be set")
        return OpenAILLMAdapter(api_key=api_key, model=settings.llm_model)

    if provider == "ollama":
        from src.infrastructure.llm.ollama_adapter import OllamaLLMAdapter

        return OllamaLLMAdapter(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )

    raise LLMUnavailableError(
        f"Unsupported LLM_PROVIDER={settings.llm_provider!r}. Use 'openai' or 'ollama'."
    )


@lru_cache
def get_embedder() -> EmbeddingPort:
    settings: Settings = get_settings()
    provider = settings.embedding_provider.strip().lower()

    if provider == "fake":
        from src.infrastructure.embeddings.fake_embedding_adapter import FakeEmbeddingAdapter

        return FakeEmbeddingAdapter(dimensions=settings.embedding_dimensions)

    if provider == "openai":
        from src.infrastructure.embeddings.openai_embedding_adapter import OpenAIEmbeddingAdapter

        api_key = settings.openai_api_key
        if not api_key:
            raise LLMUnavailableError("EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY to be set")
        return OpenAIEmbeddingAdapter(
            api_key=api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )

    raise LLMUnavailableError(
        f"Unsupported EMBEDDING_PROVIDER={settings.embedding_provider!r}. Use 'fake' or 'openai'."
    )


@lru_cache
def get_vector_store() -> VectorStorePort:
    from src.infrastructure.vector_store.qdrant_adapter import QdrantVectorStoreAdapter

    settings: Settings = get_settings()
    adapter = QdrantVectorStoreAdapter(
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection,
        dimensions=settings.embedding_dimensions,
    )
    try:
        adapter.ensure_collection()
    except VectorStoreError as exc:
        logger.warning(
            "vector_store_ensure_collection_warning", extra={"extra_data": {"error": str(exc)}}
        )
    return adapter


def get_reranker() -> RerankerPort:
    from src.infrastructure.reranker.noop_reranker import NoopReranker

    return NoopReranker()


def get_query_use_case() -> QueryUseCase:
    settings: Settings = get_settings()
    return QueryUseCase(
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        reranker=get_reranker(),
        llm=get_llm(),
        top_k=settings.top_k_retrieval,
        top_n=settings.top_n_rerank,
    )
