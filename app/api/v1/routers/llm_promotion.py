"""LLM Promotion API router."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.models import User
from app.services.promotion.llm_registry import LLMRegistry
from app.utils.dependencies import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/llm-promotion", tags=["llm-promotion"])


class RegisterProviderRequest(BaseModel):
    """Request model for LLM provider registration."""

    company_name: str = Field(..., description="Company name")
    provider_name: str = Field(..., description="Provider/LLM name")
    api_endpoint: str | None = Field(None, description="API endpoint URL")
    description: str | None = Field(None, description="Provider description")


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_provider(
    request: RegisterProviderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Register a new LLM provider (free, pending approval)."""
    try:
        registry = LLMRegistry()
        provider = registry.register_provider(
            db,
            request.company_name,
            request.provider_name,
            request.api_endpoint,
            request.description,
        )
        
        return {
            "success": True,
            "data": {
                "provider_id": provider.id,
                "provider_name": provider.provider_name,
                "status": "pending_approval",
                "message": "Provider registered successfully. Awaiting admin approval."
            }
        }
    except Exception as e:
        logger.error("llm_promotion.registration_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "REGISTRATION_FAILED",
                    "message": f"Failed to register provider: {str(e)}"
                }
            }
        ) from e


@router.get("/providers", status_code=status.HTTP_200_OK)
async def get_approved_providers(
    db: Session = Depends(get_db),
) -> dict:
    """Get all approved LLM providers."""
    try:
        registry = LLMRegistry()
        providers = registry.get_approved_providers(db)
        
        return {
            "success": True,
            "data": {
                "providers": [
                    {
                        "id": p.id,
                        "company_name": p.company_name,
                        "provider_name": p.provider_name,
                        "description": p.description,
                        "promotion_tier": p.promotion_tier,
                    }
                    for p in providers
                ]
            }
        }
    except Exception as e:
        logger.error("llm_promotion.get_providers_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "FETCH_FAILED",
                    "message": f"Failed to fetch providers: {str(e)}"
                }
            }
        ) from e

