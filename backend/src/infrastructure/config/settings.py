from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    TESTING = "testing"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.DEVELOPMENT
    log_level: str = "INFO"
    version: str = "0.1.0"

    llm_provider: str = "ollama"
    embedding_provider: str = "fake"
    openai_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "documents"

    redis_url: str = "redis://localhost:6379/0"

    chunk_max_tokens: int = Field(default=512, ge=64)
    chunk_overlap: int = Field(default=50, ge=0)
    top_k_retrieval: int = Field(default=10, ge=1)
    top_n_rerank: int = Field(default=5, ge=1)
    image_proximity_margin: float = Field(default=100.0, ge=0.0)

    storage_path: str = "./storage"
    max_upload_mb: int = Field(default=50, ge=1)

    @property
    def docs_enabled(self) -> bool:
        return self.app_env == AppEnv.DEVELOPMENT


@lru_cache
def get_settings() -> Settings:
    return Settings()
