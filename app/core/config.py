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
    
    @model_validator(mode="after")
    def load_from_env(self) -> "DatabaseSettings":
        """Load database URL from environment variable if set."""
        # Prioritize DB_URL for local Docker/PostgreSQL connections
        if os.getenv("DB_URL"):
            self.url = os.getenv("DB_URL")  # type: ignore[assignment]
        # Fallback to SUPABASE_DB_URL if DB_URL is not set (for Supabase connection)
        elif os.getenv("SUPABASE_DB_URL"):
            self.url = os.getenv("SUPABASE_DB_URL")  # type: ignore[assignment]
        return self


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


class JWTSettings(BaseSettings):
    """JWT authentication settings."""

    model_config = SettingsConfigDict(env_prefix="JWT_")

    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30  # Changed to 30 days (1 month)


class CelerySettings(BaseSettings):
    """Celery task queue settings."""

    model_config = SettingsConfigDict(env_prefix="CELERY_")

    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/0"


class SupabaseSettings(BaseSettings):
    """Supabase configuration settings."""

    model_config = SettingsConfigDict(env_prefix="SUPABASE_")

    url: str = ""
    key: str = ""

    @model_validator(mode="after")
    def load_from_env(self) -> "SupabaseSettings":
        """Load Supabase credentials from environment variables."""
        # Support both SUPABASE_URL and SUPABASE_KEY (prefixed) or direct env vars
        if not self.url:
            self.url = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_PROJECT_URL") or ""
        if not self.key:
            self.key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""
        return self


class ExternalFactCheckSettings(BaseSettings):
    """External fact check configuration settings."""

    model_config = SettingsConfigDict(env_prefix="EXTERNAL_FACT_CHECK_")

    enabled: bool = True
    serpapi_api_key: str | None = None
    top_k_results: int = 5
    claim_extraction_use_llm: bool = False
    verification_timeout: int = 30
    search_timeout: int = 10
    max_claims_per_response: int = 20

    @model_validator(mode="after")
    def load_api_key_from_env(self) -> "ExternalFactCheckSettings":
        """Load SerpAPI key from environment variable if set."""
        if not self.serpapi_api_key:
            self.serpapi_api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("EXTERNAL_FACT_CHECK_SERPAPI_API_KEY")
        return self


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
    supabase: SupabaseSettings = SupabaseSettings()
    external_fact_check: ExternalFactCheckSettings = ExternalFactCheckSettings()
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "https://ai-audit-frontend.vercel.app",
    ]

    @model_validator(mode="after")
    def load_cors_origins_from_env(self) -> "AppSettings":
        """Load CORS origins from environment variable if set."""
        cors_env = os.getenv("CORS_ORIGINS")
        if cors_env:
            # Support comma-separated list from environment variable
            origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
            if "*" in origins:
                self.cors_origins = ["*"]
            else:
                self.cors_origins = origins
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

