"""Multi-LLM response collection service.

This module handles sending the same prompt to multiple LLM APIs in parallel,
collecting responses, latency, and token usage metrics, and persisting them to the database.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import List, Optional

import structlog

from app.adapters.base import AdapterRegistry
from app.domain.schemas import AdapterInvocation, AdapterResponse
from app.services.storage import RelationalStore

logger = structlog.get_logger(__name__)


@dataclass
class MultiLLMCollectionResult:
    """Result of multi-LLM collection containing request_id and responses."""

    request_id: str
    responses: List[AdapterResponse]


class MultiLLMCollector:
    """Service for collecting responses from multiple LLM providers in parallel."""

    def __init__(self) -> None:
        """Initialize the collector with a relational store for persistence."""
        self._relational_store = RelationalStore()

    async def collect_responses(
        self,
        prompt: str,
        adapter_ids: List[str],
        request_id: Optional[str] = None,
    ) -> MultiLLMCollectionResult:
        """Send the same prompt to multiple LLM APIs in parallel and collect responses.

        Args:
            prompt: The prompt to send to all LLM providers
            adapter_ids: List of adapter/provider IDs to query (e.g., ['openai', 'gemini'])
            request_id: Optional request ID to group responses. If not provided, a UUID is generated.

        Returns:
            MultiLLMCollectionResult containing request_id and list of AdapterResponse objects

        Raises:
            ValueError: If any adapter_id is not registered
        """
        if not request_id:
            request_id = str(uuid.uuid4())

        logger.info(
            "multi_llm.collect_start",
            request_id=request_id,
            prompt_length=len(prompt),
            adapters=adapter_ids,
        )

        # Validate all adapters exist
        for adapter_id in adapter_ids:
            adapter = AdapterRegistry.get(adapter_id)
            if not adapter:
                raise ValueError(f"Adapter '{adapter_id}' is not registered")

        # Create tasks for all adapters
        tasks = []
        for adapter_id in adapter_ids:
            adapter = AdapterRegistry.get(adapter_id)
            invocation = AdapterInvocation(
                adapter_id=adapter_id,
                instructions=prompt,
            )
            task = adapter.run_async(invocation)
            tasks.append((adapter_id, task))

        # Execute all adapters in parallel
        logger.debug("multi_llm.executing_parallel", request_id=request_id, count=len(tasks))
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

        # Process results and save to database
        responses: List[AdapterResponse] = []
        for (adapter_id, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(
                    "multi_llm.adapter_error",
                    request_id=request_id,
                    adapter=adapter_id,
                    error=str(result),
                )
                # Create error response
                error_response = AdapterResponse(
                    adapter_id=adapter_id,
                    text="",
                    tokens=0,
                    latency_ms=0,
                    raw={"error": str(result)},
                    error=str(result),
                )
                responses.append(error_response)
                # Save error response to database
                await self._save_response_async(request_id, prompt, error_response)
            elif isinstance(result, AdapterResponse):
                responses.append(result)
                # Save successful response to database
                await self._save_response_async(request_id, prompt, result)
            else:
                logger.error(
                    "multi_llm.unexpected_result",
                    request_id=request_id,
                    adapter=adapter_id,
                    result_type=type(result).__name__,
                )
                error_response = AdapterResponse(
                    adapter_id=adapter_id,
                    text="",
                    tokens=0,
                    latency_ms=0,
                    raw={"error": "Unexpected result type"},
                    error="Unexpected result type",
                )
                responses.append(error_response)
                await self._save_response_async(request_id, prompt, error_response)

        logger.info(
            "multi_llm.collect_complete",
            request_id=request_id,
            total_responses=len(responses),
            successful=sum(1 for r in responses if r.error is None),
        )

        return MultiLLMCollectionResult(request_id=request_id, responses=responses)

    async def _save_response_async(
        self,
        request_id: str,
        prompt: str,
        response: AdapterResponse,
    ) -> None:
        """Save a single LLM response to the database asynchronously.

        Args:
            request_id: Request ID to group responses
            prompt: The original prompt
            response: The adapter response to save
        """
        try:
            # Extract token usage from raw metadata
            raw_metadata = response.raw
            prompt_tokens = None
            completion_tokens = None
            total_tokens = response.tokens

            # Try to extract detailed token usage from raw metadata
            if isinstance(raw_metadata, dict):
                usage = raw_metadata.get("usage", {})
                if isinstance(usage, dict):
                    prompt_tokens = usage.get("prompt_tokens")
                    completion_tokens = usage.get("completion_tokens")
                    if "total_tokens" in usage:
                        total_tokens = usage.get("total_tokens", response.tokens)

            self._relational_store.persist_llm_response(
                request_id=request_id,
                provider=response.adapter_id,
                prompt=prompt,
                raw_response=response.text,
                latency_ms=response.latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                raw_metadata=raw_metadata,
                error=response.error,
            )
        except Exception as e:
            logger.error(
                "multi_llm.save_error",
                request_id=request_id,
                adapter=response.adapter_id,
                error=str(e),
            )
            # Don't raise - we don't want to fail the entire collection if one save fails

