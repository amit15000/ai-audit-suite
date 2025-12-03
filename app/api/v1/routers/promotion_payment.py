"""Promotion Payment API router."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.models import User
from app.services.promotion.payment_service import PaymentService
from app.utils.dependencies import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/promotion-payment", tags=["promotion-payment"])


class CreatePaymentRequest(BaseModel):
    """Request model for creating a payment."""

    provider_id: str = Field(..., description="LLM provider ID")
    tier: str = Field(..., description="Promotion tier (basic, premium)")
    amount: str = Field(..., description="Payment amount")
    payment_method: str = Field(default="stripe", description="Payment method")


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_payment(
    request: CreatePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Create a payment for LLM promotion."""
    try:
        payment_service = PaymentService()
        payment = payment_service.create_payment(
            db,
            request.provider_id,
            request.tier,
            request.amount,
            request.payment_method,
        )
        
        return {
            "success": True,
            "data": {
                "payment_id": payment.id,
                "transaction_id": payment.transaction_id,
                "status": payment.payment_status,
                "message": "Payment created. Process payment to complete."
            }
        }
    except Exception as e:
        logger.error("promotion_payment.creation_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "PAYMENT_CREATION_FAILED",
                    "message": f"Failed to create payment: {str(e)}"
                }
            }
        ) from e

