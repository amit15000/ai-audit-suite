"""API router for viewing saved LLM responses."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.repositories import LLMResponseRepository
from app.services.storage import RelationalStore

router = APIRouter(prefix="/api/v1/responses", tags=["responses"])


def get_storage() -> RelationalStore:
    """Get storage instance (lazy initialization)."""
    return RelationalStore()


@router.get("/")
async def get_responses(
    request_id: Optional[str] = Query(None, description="Filter by request ID"),
    provider: Optional[str] = Query(None, description="Filter by provider (e.g., 'openai', 'gemini')"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> dict:
    """Get LLM responses from the database.

    Args:
        request_id: Optional filter by request ID
        provider: Optional filter by provider
        limit: Maximum number of results (1-500)
        offset: Number of results to skip

    Returns:
        Dictionary containing responses and metadata
    """
    try:
        storage = get_storage()
        responses = storage.get_llm_responses(
            request_id=request_id,
            provider=provider,
            limit=limit,
            offset=offset,
        )
        return {
            "total": len(responses),
            "limit": limit,
            "offset": offset,
            "responses": responses,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve responses: {str(e)}",
        ) from e


@router.get("/request/{request_id}")
async def get_responses_by_request(request_id: str) -> dict:
    """Get all responses for a specific request ID.

    Args:
        request_id: Request ID to filter by

    Returns:
        Dictionary containing all responses for the request
    """
    try:
        storage = get_storage()
        responses = storage.get_llm_responses(request_id=request_id, limit=100)
        if not responses:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No responses found for request_id: {request_id}",
            )
        return {
            "request_id": request_id,
            "total": len(responses),
            "responses": responses,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve responses: {str(e)}",
        ) from e


@router.get("/providers")
async def get_providers() -> dict:
    """Get list of all unique providers in the database.

    Returns:
        Dictionary containing list of providers
    """
    try:
        # Get all responses and extract unique providers
        storage = get_storage()
        all_responses = storage.get_llm_responses(limit=1000)
        providers = list(set(r["provider"] for r in all_responses))
        return {
            "providers": sorted(providers),
            "count": len(providers),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve providers: {str(e)}",
        ) from e


@router.get("/stats")
async def get_stats() -> dict:
    """Get statistics about saved responses.

    Returns:
        Dictionary containing statistics
    """
    try:
        storage = get_storage()
        all_responses = storage.get_llm_responses(limit=1000)
        
        if not all_responses:
            return {
                "total_responses": 0,
                "providers": {},
                "total_requests": 0,
            }

        # Count by provider
        provider_counts = {}
        request_ids = set()
        total_tokens = 0
        total_latency = 0
        successful = 0

        for response in all_responses:
            provider = response["provider"]
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            request_ids.add(response["request_id"])
            total_tokens += response.get("total_tokens", 0)
            total_latency += response.get("latency_ms", 0)
            if not response.get("error"):
                successful += 1

        return {
            "total_responses": len(all_responses),
            "total_requests": len(request_ids),
            "successful_responses": successful,
            "failed_responses": len(all_responses) - successful,
            "providers": provider_counts,
            "total_tokens": total_tokens,
            "average_latency_ms": total_latency / len(all_responses) if all_responses else 0,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats: {str(e)}",
        ) from e

