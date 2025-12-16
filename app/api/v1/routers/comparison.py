"""Comparison API router."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.models import Comparison, User
from app.domain.schemas import (
    ComparisonResponse,
    ComparisonStatusResponse,
    SubmitComparisonRequest,
)
from app.services.comparison.comparison_service import (
    create_comparison,
    get_comparison_results,
    get_comparison_status,
)
from app.services.comparison.event_manager import get_event_manager, remove_event_manager
# Removed Celery task import - processing directly without Redis
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
        comparison_id = comparison.id  # Save ID before closing session

        # Process directly in background without Redis/Celery
        import asyncio
        from app.core.database import get_session_factory
        from app.domain.models import Comparison
        from app.services.comparison.comparison_service import process_comparison
        
        # Process in background task to avoid blocking the response
        async def process_background():
            # Create a new database session for the background task
            session_factory = get_session_factory()
            background_db = session_factory()
            try:
                # Re-fetch comparison in the new session
                background_comparison = background_db.query(Comparison).filter(
                    Comparison.id == comparison_id
                ).first()
                if background_comparison:
                    # Get event manager if it exists (created by streaming endpoint)
                    from app.services.comparison.event_manager import get_event_manager
                    try:
                        event_manager = get_event_manager(comparison_id)
                    except Exception:
                        event_manager = None
                    
                    await process_comparison(background_db, background_comparison, event_manager)
            except Exception as e:
                logger.error("comparison.background_error", error=str(e), exc_info=True)
            finally:
                background_db.close()
        
        # Create background task (don't await - let it run in background)
        asyncio.create_task(process_background())
        logger.info("comparison.queued", comparison_id=comparison_id, method="direct_async")

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


@router.get(
    "/{comparison_id}/stream",
    summary="Stream comparison progress",
    description="Stream real-time updates for comparison processing using Server-Sent Events (SSE)",
)
async def stream_comparison(
    comparison_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream real-time comparison processing events."""
    try:
        # Verify comparison exists and user has access
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
        
        # Check if user owns this comparison
        if comparison.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "error": {
                        "code": "ACCESS_DENIED",
                        "message": "You do not have access to this comparison",
                    },
                },
            )
        
        # Get event manager for this comparison
        from app.services.comparison.event_manager import get_event_manager, remove_event_manager
        event_manager = get_event_manager(comparison_id)
        
        async def event_generator():
            """Generate SSE events."""
            try:
                # Send initial connection event
                import json
                from datetime import datetime
                
                initial_event = {
                    "type": "stream_connected",
                    "platform_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "comparison_id": comparison_id,
                        "status": comparison.status,
                        "progress": comparison.progress,
                    },
                }
                yield f"data: {json.dumps(initial_event)}\n\n"
                
                # Stream events from manager
                async for event_data in event_manager.stream_events():
                    yield event_data
                    
            except Exception as e:
                logger.error(
                    "comparison.stream.error",
                    comparison_id=comparison_id,
                    error=str(e),
                    exc_info=True,
                )
                # Send error event
                import json
                from datetime import datetime
                
                error_event = {
                    "type": "error",
                    "platform_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {"error": str(e)},
                }
                yield f"data: {json.dumps(error_event)}\n\n"
            finally:
                # Cleanup on disconnect
                remove_event_manager(comparison_id)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("comparison.stream.error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Failed to stream comparison: {str(e)}",
                },
            },
        ) from e

