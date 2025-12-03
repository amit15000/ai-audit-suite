"""Contradiction detection API router."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.models import User
from app.domain.schemas import (
    ContradictionDetectionResponse,
    ContradictionStatement,
    DetectContradictionsRequest,
)
from app.repositories.llm_response_repository import LLMResponseRepository
from app.services.contradiction.contradiction_detector import ContradictionDetector
from app.utils.dependencies import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/contradiction", tags=["contradiction"])


@router.post(
    "/detect",
    status_code=status.HTTP_200_OK,
    response_model=ContradictionDetectionResponse,
    summary="Detect contradictions between responses",
    description="Use an evaluator LLM to identify contradictions between multiple LLM responses",
)
async def detect_contradictions(
    request: DetectContradictionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContradictionDetectionResponse:
    """Detect contradictions between LLM responses.
    
    Can analyze either:
    1. Responses from a request_id (fetched from database)
    2. Direct responses provided in the request
    """
    try:
        responses: dict[str, str] = {}
        request_id: str | None = None
        
        # Get responses either from database or from request
        if request.request_id:
            # Fetch responses from database
            request_id = request.request_id
            llm_repo = LLMResponseRepository(session=db)
            responses_data = llm_repo.get_by_request_id(request_id)
            
            if not responses_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "success": False,
                        "error": {
                            "code": "RESPONSES_NOT_FOUND",
                            "message": f"No LLM responses found for request_id: {request_id}",
                        },
                    },
                )
            
            # Filter out error responses and build responses dict
            for response in responses_data:
                if not response.error and response.raw_response:
                    responses[response.provider] = response.raw_response
            
            if len(responses) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "success": False,
                        "error": {
                            "code": "INSUFFICIENT_RESPONSES",
                            "message": "At least 2 valid responses are required for contradiction detection",
                        },
                    },
                )
        elif request.responses:
            # Use direct responses from request
            responses = request.responses
            
            if len(responses) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "success": False,
                        "error": {
                            "code": "INSUFFICIENT_RESPONSES",
                            "message": "At least 2 valid responses are required for contradiction detection",
                        },
                    },
                )
        else:
            # This should be caught by the validator, but just in case
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "MISSING_INPUT",
                        "message": "Either 'request_id' or 'responses' must be provided",
                    },
                },
            )
        
        # Initialize contradiction detector
        detector = ContradictionDetector(evaluator_platform=request.evaluator_platform)
        
        # Detect contradictions
        try:
            contradiction_dicts = detector.detect_contradictions(
                responses=responses,
                prompt=request.prompt,
            )
        except ValueError as ve:
            error_msg = str(ve)
            logger.error("contradiction.detection.value_error", error=error_msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "API_KEY_MISSING" if "API key" in error_msg else "VALIDATION_ERROR",
                        "message": error_msg,
                    },
                },
            ) from ve
        except Exception as inner_e:
            logger.error("contradiction.detection.error", error=str(inner_e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error": {
                        "code": "DETECTION_FAILED",
                        "message": f"Failed to detect contradictions: {str(inner_e)}",
                    },
                },
            ) from inner_e
        
        # Convert to ContradictionStatement objects
        contradiction_statements = [
            ContradictionStatement(**contradiction)
            for contradiction in contradiction_dicts
        ]
        
        # Calculate severity summary
        severity_summary: dict[str, int] = {
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0,
        }
        for contradiction in contradiction_statements:
            severity = contradiction.severity.lower()
            if severity in severity_summary:
                severity_summary[severity] += 1
        
        # Build response
        response_data = ContradictionDetectionResponse(
            request_id=request_id,
            prompt=request.prompt,
            total_contradictions=len(contradiction_statements),
            contradictions=contradiction_statements,
            severity_summary=severity_summary,
        )
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error("contradiction.detect.error", error=error_msg, exc_info=True)
        
        # Provide more helpful error messages
        if "API key" in error_msg or "not configured" in error_msg:
            error_code = "API_KEY_MISSING"
            error_message = (
                "OpenAI API key is required for contradiction detection. "
                "Please set OPENAI_API_KEY or ADAPTER_OPENAI_API_KEY in your .env file "
                "and restart the server."
            )
        else:
            error_code = "INTERNAL_ERROR"
            error_message = f"Failed to detect contradictions: {error_msg}"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": error_code,
                    "message": error_message,
                },
            },
        ) from e

