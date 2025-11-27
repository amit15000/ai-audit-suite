"""Application configuration settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file explicitly to ensure environment variables are available
load_dotenv()


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    url: str = "sqlite:///var/audit.db"
    pool_size: int = 5
    max_overflow: int = 5


class StorageSettings(BaseSettings):
    """Storage configuration settings."""

    model_config = SettingsConfigDict(env_prefix="STORAGE_")

    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "w-audit"
    local_root: Path = Path("var/object_store")


class EmbeddingSettings(BaseSettings):
    """Embedding model configuration settings."""

    model_config = SettingsConfigDict(env_prefix="EMBED_")

    model_name: str = "text-embedding-3-large"


class AdapterSettings(BaseSettings):
    """Adapter configuration settings."""

    model_config = SettingsConfigDict(env_prefix="ADAPTER_")

    provider: Literal["mock", "openai"] = "mock"
    timeout_seconds: int = 30
    max_retries: int = 2
    # API keys can be set via environment variables or via prefixed settings
    # Examples: OPENAI_API_KEY, GROQ_API_KEY, HUGGINGFACE_API_KEY
    # Or: ADAPTER_OPENAI_API_KEY, ADAPTER_GROQ_API_KEY, etc.
    openai_api_key: str | None = None
    google_api_key: str | None = None
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    huggingface_api_key: str | None = None
    anthropic_api_key: str | None = None
    perplexity_api_key: str | None = None


class JWTSettings(BaseSettings):
    """JWT authentication settings."""

    model_config = SettingsConfigDict(env_prefix="JWT_")

    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class CelerySettings(BaseSettings):
    """Celery task queue settings."""

    model_config = SettingsConfigDict(env_prefix="CELERY_")

    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/0"


class AppSettings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"
    database: DatabaseSettings = DatabaseSettings()
    storage: StorageSettings = StorageSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    adapter: AdapterSettings = AdapterSettings()
    jwt: JWTSettings = JWTSettings()
    celery: CelerySettings = CelerySettings()
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> AppSettings:
    """Get cached application settings."""
    return AppSettings()

