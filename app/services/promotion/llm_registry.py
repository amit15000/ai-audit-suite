"""Service for managing LLM provider registry and promotion."""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.domain.models import LLMProvider

logger = structlog.get_logger(__name__)


class LLMRegistry:
    """Manages LLM provider registration and promotion."""

    def register_provider(
        self,
        db: Session,
        company_name: str,
        provider_name: str,
        api_endpoint: str | None = None,
        description: str | None = None,
    ) -> LLMProvider:
        """Register a new LLM provider (free, pending approval)."""
        import uuid
        
        provider = LLMProvider(
            id=str(uuid.uuid4()),
            company_name=company_name,
            provider_name=provider_name,
            api_endpoint=api_endpoint,
            description=description,
            is_approved=False,
            is_promoted=False,
            promotion_tier="free",
        )
        
        db.add(provider)
        db.commit()
        db.refresh(provider)
        
        logger.info("llm_registry.provider_registered", provider_id=provider.id, provider_name=provider_name)
        
        return provider

    def approve_provider(self, db: Session, provider_id: str) -> LLMProvider:
        """Approve a provider for display."""
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if provider:
            provider.is_approved = True
            from datetime import datetime
            provider.approved_at = datetime.utcnow()
            db.commit()
            db.refresh(provider)
        return provider

    def get_approved_providers(self, db: Session) -> list[LLMProvider]:
        """Get all approved providers."""
        return db.query(LLMProvider).filter(LLMProvider.is_approved == True).all()

