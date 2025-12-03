"""Service for collecting user preferences for LLM outputs."""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.domain.models import UserPreference

logger = structlog.get_logger(__name__)


class PreferenceCollector:
    """Collects and stores user preferences for LLM outputs."""

    def record_preference(
        self,
        db: Session,
        user_id: str,
        preferred_provider: str,
        comparison_id: str | None = None,
        reason: str | None = None,
    ) -> UserPreference:
        """Record a user's preference for an LLM output."""
        preference = UserPreference(
            user_id=user_id,
            preferred_provider=preferred_provider,
            comparison_id=comparison_id,
            preference_reason=reason,
        )
        
        db.add(preference)
        db.commit()
        db.refresh(preference)
        
        logger.info("preference.recorded", user_id=user_id, preferred_provider=preferred_provider)
        
        return preference

    def get_preference_analytics(self, db: Session) -> dict[str, Any]:
        """Get analytics on user preferences."""
        from sqlalchemy import func
        
        # Count preferences by provider
        provider_counts = (
            db.query(
                UserPreference.preferred_provider,
                func.count(UserPreference.id).label("count")
            )
            .group_by(UserPreference.preferred_provider)
            .all()
        )
        
        return {
            "provider_preferences": {provider: count for provider, count in provider_counts},
            "total_preferences": sum(count for _, count in provider_counts)
        }

