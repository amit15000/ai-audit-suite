from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_")

    url: str = "sqlite:///var/audit.db"
    pool_size: int = 5
    max_overflow: int = 5


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STORAGE_")

    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "w-audit"
    local_root: Path = Path("var/object_store")


class EmbeddingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMBED_")

    model_name: str = "text-embedding-3-large"


class AdapterSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADAPTER_")

    provider: Literal["mock"] = "mock"
    timeout_seconds: int = 30
    max_retries: int = 2


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"
    database: DatabaseSettings = DatabaseSettings()
    storage: StorageSettings = StorageSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    adapter: AdapterSettings = AdapterSettings()


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()

