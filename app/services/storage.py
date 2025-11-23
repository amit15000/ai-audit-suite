from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import get_settings


class ObjectStoreClient:
    def __init__(self) -> None:
        settings = get_settings().storage
        self._root = Path(settings.local_root)
        self._root.mkdir(parents=True, exist_ok=True)

    def persist(self, key: str, payload: Dict[str, Any]) -> str:
        target = self._root / f"{key}.json"
        target.write_text(json.dumps(payload, indent=2))
        return str(target)


class RelationalStore:
    def __init__(self) -> None:
        settings = get_settings().database
        self._engine: Engine = create_engine(settings.url, echo=False, future=True)
        self._dialect = self._engine.url.get_backend_name()
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        if self._dialect == "sqlite":
            ddl = """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        else:
            ddl = """
            CREATE TABLE IF NOT EXISTS audit_events (
                id SERIAL PRIMARY KEY,
                job_id TEXT NOT NULL,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        with self._engine.begin() as conn:
            conn.execute(text(ddl))

    def persist_event(self, job_id: str, payload: Dict[str, Any]) -> None:
        if self._dialect == "sqlite":
            stmt = text(
                "INSERT INTO audit_events (job_id, payload) VALUES (:job_id, :payload)"
            )
        else:
            stmt = text(
                "INSERT INTO audit_events (job_id, payload) VALUES (:job_id, :payload::jsonb)"
            )
        with self._engine.begin() as conn:
            conn.execute(stmt, {"job_id": job_id, "payload": json.dumps(payload)})

