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
    # API keys can be set via environment variables (OPENAI_API_KEY, GOOGLE_API_KEY, GEMINI_API_KEY)
    # or via prefixed settings (ADAPTER_OPENAI_API_KEY, ADAPTER_GOOGLE_API_KEY, ADAPTER_GEMINI_API_KEY)
    openai_api_key: str | None = None
    google_api_key: str | None = None
    gemini_api_key: str | None = None


class AppSettings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"
    database: DatabaseSettings = DatabaseSettings()
    storage: StorageSettings = StorageSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    adapter: AdapterSettings = AdapterSettings()


@lru_cache
def get_settings() -> AppSettings:
    """Get cached application settings."""
    return AppSettings()

