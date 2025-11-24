"""Repository for LLM response data access."""
from __future__ import annotations

from typing import Any

from app.domain.models import LLMResponse
from app.repositories.base import BaseRepository


class LLMResponseRepository(BaseRepository[LLMResponse]):
    """Repository for LLM response data access."""

    def create(
        self,
        request_id: str,
        provider: str,
        prompt: str,
        raw_response: str,
        latency_ms: int,
        total_tokens: int,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        raw_metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> LLMResponse:
        """Create a new LLM response record.

        Args:
            request_id: Request ID to group responses
            provider: LLM provider/adapter ID
            prompt: The prompt sent to the LLM
            raw_response: Raw response text from the LLM
            latency_ms: Response latency in milliseconds
            total_tokens: Total tokens used
            prompt_tokens: Number of tokens in the prompt (optional)
            completion_tokens: Number of tokens in the completion (optional)
            raw_metadata: Additional raw metadata (optional)
            error: Error message if the request failed (optional)

        Returns:
            Created LLMResponse instance
        """
        session = self._get_session()
        try:
            llm_response = LLMResponse(
                request_id=request_id,
                provider=provider,
                prompt=prompt,
                raw_response=raw_response,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                raw_metadata=raw_metadata,
                error=error,
            )
            session.add(llm_response)
            session.commit()
            session.refresh(llm_response)
            return llm_response
        except Exception:
            session.rollback()
            raise

    def get_by_request_id(self, request_id: str) -> list[LLMResponse]:
        """Get all LLM responses for a request ID.

        Args:
            request_id: Request ID to filter by

        Returns:
            List of LLMResponse instances
        """
        session = self._get_session()
        return (
            session.query(LLMResponse)
            .filter(LLMResponse.request_id == request_id)
            .order_by(LLMResponse.created_at.desc())
            .all()
        )

    def get_by_provider(self, provider: str) -> list[LLMResponse]:
        """Get all LLM responses for a provider.

        Args:
            provider: Provider ID to filter by

        Returns:
            List of LLMResponse instances
        """
        session = self._get_session()
        return (
            session.query(LLMResponse)
            .filter(LLMResponse.provider == provider)
            .order_by(LLMResponse.created_at.desc())
            .all()
        )

    def get_all(
        self,
        request_id: str | None = None,
        provider: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get multiple LLM responses with optional filters.

        Args:
            request_id: Optional filter by request ID
            provider: Optional filter by provider
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of LLM response dictionaries
        """
        session = self._get_session()
        query = session.query(LLMResponse)
        if request_id:
            query = query.filter(LLMResponse.request_id == request_id)
        if provider:
            query = query.filter(LLMResponse.provider == provider)
        responses = (
            query.order_by(LLMResponse.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return [response.to_dict() for response in responses]

