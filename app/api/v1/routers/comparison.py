"""Comparison API router."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.models import User
from app.domain.schemas import (
    ComparisonResponse,
    ComparisonStatusResponse,
    SubmitComparisonRequest,
)
from app.services.comparison_service import (
    create_comparison,
    get_comparison_results,
    get_comparison_status,
)
from app.tasks.comparison_tasks import process_comparison_task
from app.utils.dependencies import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/comparison", tags=["comparison"])


@router.post(
    "/submit",
    status_code=status.HTTP_200_OK,
    summary="Submit prompt for comparison",
    description="Submit a prompt to compare across multiple AI platforms",
)
async def submit_comparison(
    request: SubmitComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Submit a prompt for comparison across multiple AI platforms."""
    try:
        # Validate platforms
        from app.utils.platform_mapping import is_valid_platform
        
        for platform_id in request.platforms:
            if not is_valid_platform(platform_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "success": False,
                        "error": {
                            "code": "INVALID_PLATFORM",
                            "message": f"Platform '{platform_id}' is not recognized",
                        },
                    },
                )
        
        if not is_valid_platform(request.judge):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "INVALID_PLATFORM",
                        "message": f"Judge platform '{request.judge}' is not recognized",
                    },
                },
            )

        # Create comparison
        comparison = create_comparison(db, current_user.id, request)

        # Queue async processing - try Celery, fallback to direct async if Redis unavailable
        try:
            # Try to use Celery for async processing
            process_comparison_task.delay(comparison.id)
            logger.info("comparison.queued", comparison_id=comparison.id, method="celery")
        except Exception as celery_error:
            # If Celery/Redis is not available, process directly in background
            logger.warning(
                "celery.unavailable",
                error=str(celery_error),
                message="Celery unavailable, processing directly in background",
            )
            import asyncio
            from app.services.comparison_service import process_comparison
            # Process in background task to avoid blocking the response
            async def process_background():
                try:
                    await process_comparison(db, comparison)
                except Exception as e:
                    logger.error("comparison.background_error", error=str(e), exc_info=True)
            # Create background task (don't await - let it run in background)
            asyncio.create_task(process_background())
            logger.info("comparison.queued", comparison_id=comparison.id, method="direct_async")

        return {
            "success": True,
            "data": {
                "comparisonId": comparison.id,
                "messageId": comparison.message_id,
                "status": comparison.status,
                "estimatedTime": 30,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("comparison.submit.error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "PROCESSING_FAILED",
                    "message": f"Failed to submit comparison: {str(e)}",
                },
            },
        ) from e


@router.get(
    "/{comparison_id}/results",
    status_code=status.HTTP_200_OK,
    summary="Get comparison results",
    description="Get the results of a comparison",
)
async def get_results(
    comparison_id: str,
    judge: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get comparison results."""
    try:
        results = get_comparison_results(db, comparison_id, judge)
        
        if not results:
            # Check if comparison exists but is still processing
            from app.domain.models import Comparison
            comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
            
            if not comparison:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "success": False,
                        "error": {
                            "code": "COMPARISON_NOT_FOUND",
                            "message": f"Comparison with ID {comparison_id} not found",
                        },
                    },
                )
            
            # Return status response if still processing
            if comparison.status in ["queued", "processing"]:
                raise HTTPException(
                    status_code=status.HTTP_202_ACCEPTED,
                    detail={
                        "success": True,
                        "data": {
                            "comparisonId": comparison.id,
                            "status": comparison.status,
                            "progress": comparison.progress,
                            "estimatedTimeRemaining": max(0, 30 - (comparison.progress * 30 // 100)),
                        },
                    },
                )
            
            # If failed, return error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error": {
                        "code": "PROCESSING_FAILED",
                        "message": comparison.error_message or "Comparison processing failed",
                    },
                },
            )
        
        return {
            "success": True,
            "data": results.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("comparison.results.error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Failed to get results: {str(e)}",
                },
            },
        ) from e


@router.get(
    "/{comparison_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Get comparison status",
    description="Get the status of a comparison",
)
async def get_status(
    comparison_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get comparison status."""
    try:
        status_data = get_comparison_status(db, comparison_id)
        
        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "COMPARISON_NOT_FOUND",
                        "message": f"Comparison with ID {comparison_id} not found",
                    },
                },
            )
        
        return {
            "success": True,
            "data": status_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("comparison.status.error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Failed to get status: {str(e)}",
                },
            },
        ) from e

