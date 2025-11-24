"""Repository for audit events."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.domain.models import AuditEvent
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditEvent]):
    """Repository for audit event data access."""

    def create(self, job_id: str, payload: dict[str, Any]) -> AuditEvent:
        """Create a new audit event.

        Args:
            job_id: Job identifier
            payload: Event payload data

        Returns:
            Created AuditEvent instance
        """
        # Convert datetime objects to ISO format strings for JSON serialization
        def serialize_datetime(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        # Recursively serialize datetime objects in payload
        serialized_payload = json.loads(json.dumps(payload, default=serialize_datetime))

        session = self._get_session()
        try:
            event = AuditEvent(job_id=job_id, payload=serialized_payload)
            session.add(event)
            session.commit()
            session.refresh(event)
            return event
        except Exception:
            session.rollback()
            raise

    def get_by_job_id(self, job_id: str) -> AuditEvent | None:
        """Get audit event by job ID.

        Args:
            job_id: Job identifier

        Returns:
            AuditEvent if found, None otherwise
        """
        session = self._get_session()
        return session.query(AuditEvent).filter(AuditEvent.job_id == job_id).first()

    def get_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get multiple audit events.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of audit event dictionaries
        """
        session = self._get_session()
        events = (
            session.query(AuditEvent)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return [event.to_dict() for event in events]

