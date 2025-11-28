"""Similarity analysis API router."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.models import User
from app.domain.schemas import (
    ProcessSimilarityRequest,
    SimilarityAnalysisResponse,
)
from app.repositories.embedding_repository import (
    EmbeddingRepository,
    SimilarityAnalysisRepository,
)
from app.repositories.llm_response_repository import LLMResponseRepository
from app.services.embedding.similarity_processor import SimilarityProcessor
from app.utils.dependencies import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/similarity", tags=["similarity"])


@router.post(
    "/process",
    status_code=status.HTTP_200_OK,
    response_model=SimilarityAnalysisResponse,
    summary="Process similarity analysis",
    description="Generate embeddings and compute similarity analysis for LLM responses",
)
async def process_similarity(
    request: ProcessSimilarityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Process similarity analysis for a request ID with existing LLM responses."""
    try:
        # Get LLM responses for the request_id
        llm_repo = LLMResponseRepository(session=db)
        responses_data = llm_repo.get_by_request_id(request.request_id)

        if not responses_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "RESPONSES_NOT_FOUND",
                        "message": f"No LLM responses found for request_id: {request.request_id}",
                    },
                },
            )

        # Filter out error responses and build responses dict
        responses: dict[str, str] = {}
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
                        "message": "At least 2 valid responses are required for similarity analysis",
                    },
                },
            )

        # Process similarity analysis
        try:
            embedding_repo = EmbeddingRepository(session=db)
            similarity_repo = SimilarityAnalysisRepository(session=db)
            processor = SimilarityProcessor(
                embedding_repo=embedding_repo,
                similarity_repo=similarity_repo,
            )

            analysis_result = await processor.process_responses(
                request_id=request.request_id,
                responses=responses,
                persist=request.persist,
            )
        except ValueError as ve:
            # Handle specific ValueError (e.g., API key missing)
            error_msg = str(ve)
            logger.error("similarity.process.value_error", error=error_msg)
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
            # Re-raise to be caught by outer handler
            raise

        # Build response
        from app.domain.schemas import OutlierDetail, SimilarityStatistics

        outlier_details = [
            OutlierDetail(**detail)
            for detail in analysis_result["outlier_analysis"]["outlier_details"]
        ]

        stats = analysis_result["outlier_analysis"]["statistics"]
        statistics = SimilarityStatistics(
            mean=stats["mean"],
            std_dev=stats["std_dev"],
            min=stats["min"],
            max=stats["max"],
            count=stats["count"],
        )

        response_data = SimilarityAnalysisResponse(
            request_id=request.request_id,
            similarity_matrix=analysis_result["similarity_matrix"],
            consensus_scores=analysis_result["consensus_scores"],
            outliers=analysis_result["outliers"],
            outlier_threshold=analysis_result["outlier_analysis"]["threshold"],
            statistics=statistics,
            outlier_details=outlier_details,
        )

        # Return the response data directly (it already matches the response model)
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error("similarity.process.error", error=error_msg, exc_info=True)
        
        # Provide more helpful error messages
        if "API key" in error_msg or "not configured" in error_msg:
            error_code = "API_KEY_MISSING"
            error_message = (
                "OpenAI API key is required for embedding generation. "
                "Please set OPENAI_API_KEY or ADAPTER_OPENAI_API_KEY in your .env file "
                "and restart the server."
            )
        else:
            error_code = "PROCESSING_FAILED"
            error_message = f"Failed to process similarity analysis: {error_msg}"
        
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


@router.get(
    "/{request_id}",
    status_code=status.HTTP_200_OK,
    response_model=SimilarityAnalysisResponse,
    summary="Get similarity analysis",
    description="Get stored similarity analysis for a request ID",
)
async def get_similarity_analysis(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get stored similarity analysis for a request ID."""
    try:
        embedding_repo = EmbeddingRepository(session=db)
        similarity_repo = SimilarityAnalysisRepository(session=db)
        processor = SimilarityProcessor(
            embedding_repo=embedding_repo,
            similarity_repo=similarity_repo,
        )

        analysis_result = await processor.get_analysis(request_id)

        if not analysis_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "ANALYSIS_NOT_FOUND",
                        "message": f"No similarity analysis found for request_id: {request_id}",
                    },
                },
            )

        # Build response
        from app.domain.schemas import OutlierDetail, SimilarityStatistics

        outlier_analysis = analysis_result["outlier_analysis"]
        outlier_details = [
            OutlierDetail(**detail) for detail in outlier_analysis.get("outlier_details", [])
        ]

        stats = outlier_analysis.get("statistics", {})
        statistics = SimilarityStatistics(
            mean=stats.get("mean", 0.0),
            std_dev=stats.get("std_dev", 0.0),
            min=stats.get("min", 0.0),
            max=stats.get("max", 0.0),
            count=stats.get("count", 0),
        )

        response_data = SimilarityAnalysisResponse(
            request_id=request_id,
            similarity_matrix=analysis_result["similarity_matrix"],
            consensus_scores=analysis_result["consensus_scores"],
            outliers=analysis_result.get("outliers", []),
            outlier_threshold=outlier_analysis.get("threshold"),
            statistics=statistics,
            outlier_details=outlier_details,
        )

        # Return the response data directly (it already matches the response model)
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error("similarity.get.error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Failed to get similarity analysis: {str(e)}",
                },
            },
        ) from e

