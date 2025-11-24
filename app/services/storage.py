"""Storage services for object and relational data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.core.config import get_settings
from app.core.database import init_db
from app.repositories import AuditRepository, LLMResponseRepository


class ObjectStoreClient:
    """Client for object storage (S3-compatible or local file system)."""

    def __init__(self) -> None:
        settings = get_settings().storage
        self._root = Path(settings.local_root)
        self._root.mkdir(parents=True, exist_ok=True)

    def persist(self, key: str, payload: Dict[str, Any]) -> str:
        """Persist a JSON payload to object storage.

        Args:
            key: Storage key/identifier
            payload: Data to persist

        Returns:
            Path to the stored file
        """
        target = self._root / f"{key}.json"
        target.write_text(json.dumps(payload, indent=2))
        return str(target)


class RelationalStore:
    """Relational database store using repository pattern."""

    def __init__(self) -> None:
        # Initialize database tables on first use
        init_db()
        self._audit_repo = AuditRepository()
        self._llm_response_repo = LLMResponseRepository()

    def persist_event(self, job_id: str, payload: Dict[str, Any]) -> None:
        """Persist an audit event using repository.

        Args:
            job_id: Job identifier
            payload: Event payload data
        """
        try:
            self._audit_repo.create(job_id=job_id, payload=payload)
        finally:
            self._audit_repo.close()

    def get_event(self, job_id: str) -> Dict[str, Any] | None:
        """Retrieve an audit event by job_id.

        Args:
            job_id: Job identifier

        Returns:
            Event dictionary if found, None otherwise
        """
        try:
            event = self._audit_repo.get_by_job_id(job_id)
            if event:
                return event.to_dict()
            return None
        finally:
            self._audit_repo.close()

    def get_events(
        self, limit: int = 100, offset: int = 0
    ) -> list[Dict[str, Any]]:
        """Retrieve multiple audit events.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of audit event dictionaries
        """
        try:
            return self._audit_repo.get_all(limit=limit, offset=offset)
        finally:
            self._audit_repo.close()

    def persist_llm_response(
        self,
        request_id: str,
        provider: str,
        prompt: str,
        raw_response: str,
        latency_ms: int,
        total_tokens: int,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        raw_metadata: Dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Persist an LLM response to the database.

        Args:
            request_id: Request ID to group responses from the same request
            provider: LLM provider/adapter ID (e.g., 'openai', 'gemini')
            prompt: The prompt sent to the LLM
            raw_response: Raw response text from the LLM
            latency_ms: Response latency in milliseconds
            total_tokens: Total tokens used
            prompt_tokens: Number of tokens in the prompt (optional)
            completion_tokens: Number of tokens in the completion (optional)
            raw_metadata: Additional raw metadata from the API response (optional)
            error: Error message if the request failed (optional)
        """
        try:
            self._llm_response_repo.create(
                request_id=request_id,
                provider=provider,
                prompt=prompt,
                raw_response=raw_response,
                latency_ms=latency_ms,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                raw_metadata=raw_metadata,
                error=error,
            )
        finally:
            self._llm_response_repo.close()

    def get_llm_responses(
        self,
        request_id: str | None = None,
        provider: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Dict[str, Any]]:
        """Retrieve LLM responses from the database.

        Args:
            request_id: Optional filter by request ID
            provider: Optional filter by provider
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of LLM response dictionaries
        """
        try:
            return self._llm_response_repo.get_all(
                request_id=request_id, provider=provider, limit=limit, offset=offset
            )
        finally:
            self._llm_response_repo.close()
