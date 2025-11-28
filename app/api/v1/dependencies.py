"""API dependencies for dependency injection."""
from __future__ import annotations

from app.repositories import AuditRepository, LLMResponseRepository
from app.services.llm.multi_llm_collector import MultiLLMCollector


def get_audit_repository() -> AuditRepository:
    """Get audit repository instance."""
    return AuditRepository()


def get_llm_response_repository() -> LLMResponseRepository:
    """Get LLM response repository instance."""
    return LLMResponseRepository()


def get_multi_llm_collector() -> MultiLLMCollector:
    """Get multi-LLM collector service instance."""
    return MultiLLMCollector()

