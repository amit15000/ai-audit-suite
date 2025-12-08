"""Application configuration settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import os

from dotenv import load_dotenv
from pydantic import model_validator
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
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_region: str | None = None
    use_s3: bool = True  # Set to False to use local filesystem instead
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

    @model_validator(mode="after")
    def load_api_keys_from_env(self) -> "AdapterSettings":
        """Load API keys from environment variables (check both prefixed and non-prefixed)."""
        # Check OPENAI_API_KEY (direct) or ADAPTER_OPENAI_API_KEY (prefixed)
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ADAPTER_OPENAI_API_KEY")
        if not self.google_api_key:
            self.google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("ADAPTER_GOOGLE_API_KEY") or os.getenv("ADAPTER_GEMINI_API_KEY")
        if not self.gemini_api_key:
            self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("ADAPTER_GEMINI_API_KEY") or os.getenv("ADAPTER_GOOGLE_API_KEY")
        if not self.groq_api_key:
            self.groq_api_key = os.getenv("GROQ_API_KEY") or os.getenv("ADAPTER_GROQ_API_KEY")
        if not self.huggingface_api_key:
            self.huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("ADAPTER_HUGGINGFACE_API_KEY")
        if not self.anthropic_api_key:
            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ADAPTER_ANTHROPIC_API_KEY")
        if not self.perplexity_api_key:
            self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY") or os.getenv("ADAPTER_PERPLEXITY_API_KEY")
        return self


class ExternalAPISettings(BaseSettings):
    """External API configuration settings for fact-checking and verification."""

    model_config = SettingsConfigDict(env_prefix="EXTERNAL_API_")

    # Google Custom Search API (for factual accuracy checking)
    google_custom_search_api_key: str | None = None
    google_custom_search_cx: str | None = None
    
    # Perspective API (for toxicity detection)
    perspective_api_key: str | None = None
    
    # Copyscape API (for plagiarism checking)
    copyscape_api_key: str | None = None
    copyscape_username: str | None = None

    @model_validator(mode="after")
    def load_api_keys_from_env(self) -> "ExternalAPISettings":
        """Load external API keys from environment variables."""
        if not self.google_custom_search_api_key:
            self.google_custom_search_api_key = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY") or os.getenv("EXTERNAL_API_GOOGLE_CUSTOM_SEARCH_API_KEY")
        if not self.google_custom_search_cx:
            self.google_custom_search_cx = os.getenv("GOOGLE_CUSTOM_SEARCH_CX") or os.getenv("EXTERNAL_API_GOOGLE_CUSTOM_SEARCH_CX")
        if not self.perspective_api_key:
            self.perspective_api_key = os.getenv("PERSPECTIVE_API_KEY") or os.getenv("EXTERNAL_API_PERSPECTIVE_API_KEY")
        if not self.copyscape_api_key:
            self.copyscape_api_key = os.getenv("COPYSCAPE_API_KEY") or os.getenv("EXTERNAL_API_COPYSCAPE_API_KEY")
        if not self.copyscape_username:
            self.copyscape_username = os.getenv("COPYSCAPE_USERNAME") or os.getenv("EXTERNAL_API_COPYSCAPE_USERNAME")
        return self


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
    external_api: ExternalAPISettings = ExternalAPISettings()
    cors_origins: list[str] = ["*"]  # Allow all origins by default

    @model_validator(mode="after")
    def load_cors_origins_from_env(self) -> "AppSettings":
        """Load CORS origins from environment variable if set."""
        cors_env = os.getenv("CORS_ORIGINS")
        if cors_env:
            # Support comma-separated list from environment variable
            # If "*" is provided, allow all origins
            origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
            if "*" in origins:
                self.cors_origins = ["*"]
            else:
                self.cors_origins = origins
        # Default to allowing all origins if not specified
        return self


_settings_cache: AppSettings | None = None


def get_settings() -> AppSettings:
    """Get application settings (cached but can be cleared)."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = AppSettings()
    return _settings_cache


def clear_settings_cache() -> None:
    """Clear the settings cache (useful for testing or reloading config)."""
    global _settings_cache
    _settings_cache = None

