"""SQLAlchemy ORM models for database tables."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class AuditEvent(Base):
    """ORM model for audit events table."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AuditEvent(id={self.id}, job_id={self.job_id}, created_at={self.created_at})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LLMResponse(Base):
    """ORM model for storing LLM API responses with metrics."""

    __tablename__ = "llm_responses"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, nullable=False, index=True, comment="Groups responses from the same request")
    provider = Column(String, nullable=False, index=True, comment="LLM provider/adapter ID (e.g., 'openai', 'gemini')")
    prompt = Column(Text, nullable=False, comment="The prompt sent to the LLM")
    raw_response = Column(Text, nullable=False, comment="Raw response text from the LLM")
    latency_ms = Column(Integer, nullable=False, comment="Response latency in milliseconds")
    prompt_tokens = Column(Integer, nullable=True, comment="Number of tokens in the prompt")
    completion_tokens = Column(Integer, nullable=True, comment="Number of tokens in the completion")
    total_tokens = Column(Integer, nullable=False, comment="Total tokens used")
    raw_metadata = Column(JSON, nullable=True, comment="Additional raw metadata from the API response")
    error = Column(Text, nullable=True, comment="Error message if the request failed")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<LLMResponse(id={self.id}, request_id={self.request_id}, "
            f"provider={self.provider}, latency_ms={self.latency_ms}, "
            f"total_tokens={self.total_tokens})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "provider": self.provider,
            "prompt": self.prompt,
            "raw_response": self.raw_response,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "raw_metadata": self.raw_metadata,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

