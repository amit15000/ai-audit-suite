"""User Preference API router."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.models import User
from app.services.preference.preference_collector import PreferenceCollector
from app.utils.dependencies import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/user-preference", tags=["user-preference"])


class RecordPreferenceRequest(BaseModel):
    """Request model for recording user preference."""

    preferred_provider: str = Field(..., description="Preferred LLM provider")
    comparison_id: str | None = Field(None, description="Comparison ID if applicable")
    reason: str | None = Field(None, description="Reason for preference")


@router.post("/record", status_code=status.HTTP_201_CREATED)
async def record_preference(
    request: RecordPreferenceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Record user's preference for an LLM output."""
    try:
        collector = PreferenceCollector()
        preference = collector.record_preference(
            db,
            current_user.id,
            request.preferred_provider,
            request.comparison_id,
            request.reason,
        )
        
        return {
            "success": True,
            "data": {
                "preference_id": preference.id,
                "preferred_provider": preference.preferred_provider,
                "message": "Preference recorded successfully"
            }
        }
    except Exception as e:
        logger.error("user_preference.recording_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "RECORDING_FAILED",
                    "message": f"Failed to record preference: {str(e)}"
                }
            }
        ) from e


@router.get("/analytics", status_code=status.HTTP_200_OK)
async def get_preference_analytics(
    db: Session = Depends(get_db),
) -> dict:
    """Get analytics on user preferences."""
    try:
        collector = PreferenceCollector()
        analytics = collector.get_preference_analytics(db)
        
        return {
            "success": True,
            "data": analytics
        }
    except Exception as e:
        logger.error("user_preference.analytics_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "ANALYTICS_FAILED",
                    "message": f"Failed to get analytics: {str(e)}"
                }
            }
        ) from e

