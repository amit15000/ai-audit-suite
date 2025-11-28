"""Multi-LLM response collection API router.

This router provides endpoints for sending the same prompt to multiple LLM APIs
in parallel and collecting their responses with metrics.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status

from app.domain.schemas import AdapterResponse, MultiLLMRequest, MultiLLMResponse, MultiLLMResponseItem
from app.services.llm.multi_llm_collector import MultiLLMCollector

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/multi-llm", tags=["multi-llm"])

# Initialize the collector service
_collector = MultiLLMCollector()


@router.post(
    "/collect",
    response_model=MultiLLMResponse,
    status_code=status.HTTP_200_OK,
    summary="Collect responses from multiple LLMs simultaneously",
    description="""
    Send the same prompt to multiple LLM providers in parallel and collect their responses.
    
    This endpoint:
    - Sends the prompt to all specified LLM providers simultaneously (async)
    - Collects responses, latency, and token usage metrics
    - Automatically saves all responses to the database
    - Returns aggregated results with success/failure counts
    
    **Available adapters:**
    - `openai`: OpenAI GPT models
    - `gemini`: Google Gemini models (free tier available)
    - `groq`: Groq API (very fast, free tier available)
    - `huggingface`: Hugging Face Inference API (free for many models)
    - `mock`: Mock adapter for testing
    """,
)
async def collect_multi_llm_responses(request: MultiLLMRequest) -> MultiLLMResponse:
    """Collect responses from multiple LLM providers in parallel.
    
    Args:
        request: MultiLLMRequest containing prompt and adapter_ids
        
    Returns:
        MultiLLMResponse with all collected responses and metrics (includes auto-generated request_id)
        
    Raises:
        HTTPException: If any adapter is not registered or if collection fails
    """
    try:
        logger.info(
            "multi_llm.api.collect_start",
            prompt_length=len(request.prompt),
            adapter_count=len(request.adapter_ids),
            adapters=request.adapter_ids,
        )

        # Collect responses using the service (request_id is auto-generated)
        collection_result = await _collector.collect_responses(
            prompt=request.prompt,
            adapter_ids=request.adapter_ids,
            request_id=None,  # Auto-generate UUID
        )

        # Get the request_id from the collection result
        request_id = collection_result.request_id
        adapter_responses = collection_result.responses

        # Convert AdapterResponse to MultiLLMResponseItem
        response_items: list[MultiLLMResponseItem] = []
        for adapter_response in adapter_responses:
            # Extract token usage from raw metadata
            prompt_tokens = None
            completion_tokens = None
            raw_metadata = adapter_response.raw

            if isinstance(raw_metadata, dict):
                usage = raw_metadata.get("usage", {})
                if isinstance(usage, dict):
                    prompt_tokens = usage.get("prompt_tokens")
                    completion_tokens = usage.get("completion_tokens")

            response_items.append(
                MultiLLMResponseItem(
                    adapter_id=adapter_response.adapter_id,
                    text=adapter_response.text,
                    tokens=adapter_response.tokens,
                    latency_ms=adapter_response.latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    raw_metadata=raw_metadata,
                    error=adapter_response.error,
                    success=adapter_response.error is None,
                )
            )

        successful_count = sum(1 for item in response_items if item.success)
        failed_count = len(response_items) - successful_count

        response = MultiLLMResponse(
            request_id=request_id,
            prompt=request.prompt,
            responses=response_items,
            total_responses=len(response_items),
            successful_responses=successful_count,
            failed_responses=failed_count,
        )

        logger.info(
            "multi_llm.api.collect_complete",
            request_id=request_id,
            total=len(response_items),
            successful=successful_count,
            failed=failed_count,
        )

        return response

    except ValueError as e:
        logger.error("multi_llm.api.validation_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("multi_llm.api.collection_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to collect LLM responses: {str(e)}",
        ) from e

