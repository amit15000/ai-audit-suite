"""Google Gemini adapter implementation using httpx."""
from __future__ import annotations

import os
import time
from typing import Any, Dict

import httpx
import structlog

from app.adapters.base import AdapterRegistry, BaseAdapter
from app.core.config import get_settings
from app.domain.schemas import AdapterInvocation, AdapterResponse

logger = structlog.get_logger(__name__)


class GeminiAdapter(BaseAdapter):
    """Google Gemini adapter using httpx and v1beta API."""

    name = "gemini"

    def __init__(self) -> None:
        super().__init__()
        self._client: httpx.AsyncClient | None = None
        self._api_key: str | None = None
        self._model: str = "gemini-2.5-flash"
        settings = get_settings()
        self._timeout = settings.adapter.timeout_seconds

    def _get_api_key(self) -> str:
        """Get Gemini API key from settings or environment."""
        if self._api_key:
            return self._api_key

        settings = get_settings()
        # Try multiple possible environment variable names
        api_key = (
            settings.adapter.gemini_api_key
            or settings.adapter.google_api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )

        if not api_key:
            raise ValueError(
                "Gemini API key is required. Set it in .env file as:\n"
                "- GEMINI_API_KEY=your_key\n"
                "- GOOGLE_API_KEY=your_key\n"
                "- ADAPTER_GEMINI_API_KEY=your_key\n"
                "- ADAPTER_GOOGLE_API_KEY=your_key"
            )

        self._api_key = api_key
        return api_key

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of Gemini HTTP client."""
        if self._client is None:
            api_key = self._get_api_key()
            # Use v1beta endpoint as per official documentation
            base_url = "https://generativelanguage.googleapis.com/v1beta"

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=10.0),
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                base_url=base_url,
            )
        return self._client

    async def invoke_async(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Invoke Gemini API asynchronously using httpx."""
        started = time.perf_counter()
        client = self._get_client()

        try:
            url = f"/models/{self._model}:generateContent"
            logger.debug("Calling Gemini API", url=url, model=self._model)

            # Request body format as per official documentation
            request_body = {
                "contents": [
                    {
                        "parts": [
                            {"text": invocation.instructions}
                        ]
                    }
                ]
            }

            response = await client.post(url, json=request_body)
            response.raise_for_status()
            data = response.json()

            # Validate response structure
            candidates = data.get("candidates")
            if not candidates:
                error_msg = data.get("error", {}).get("message", "No candidates in response")
                logger.error("Gemini API returned no candidates", error=error_msg, response=data)
                raise ValueError(f"Gemini API error: {error_msg}")

            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts") or []

            if not parts:
                raise ValueError("Gemini API: missing parts in content")

            first_part = parts[0]
            text = first_part.get("text", "")

            if text is None or text == "":
                raise ValueError("Gemini API returned empty text")

            # Calculate latency
            latency_ms = int((time.perf_counter() - started) * 1000)

            # Estimate tokens (Gemini doesn't provide exact token counts in free tier)
            estimated_tokens = len(text.split()) * 1.3

            # Extract usage info if available
            usage_info = candidate.get("usageMetadata", {})
            prompt_tokens = usage_info.get("promptTokenCount")
            completion_tokens = usage_info.get("candidatesTokenCount")
            total_tokens = usage_info.get("totalTokenCount") or int(estimated_tokens)

            raw_payload: Dict[str, Any] = {
                "adapter_id": invocation.adapter_id,
                "model": self._model,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
                "response_id": candidate.get("finishReason", "unknown"),
                "candidates": len(candidates),
            }

            logger.info(
                "Gemini response generated",
                model=self._model,
                prompt_length=len(invocation.instructions),
                response_length=len(text),
                latency_ms=latency_ms,
            )

            return AdapterResponse(
                adapter_id=invocation.adapter_id,
                text=text,
                tokens=total_tokens,
                latency_ms=latency_ms,
                raw=raw_payload,
            )

        except httpx.HTTPStatusError as e:
            # Extract error details from response
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", {}).get("message", str(e))
            except Exception:
                error_detail = f"HTTP {e.response.status_code}: {e.response.text[:200]}"

            logger.error(
                "Gemini HTTP error",
                status_code=e.response.status_code,
                error=error_detail,
                model=self._model,
            )

            latency_ms = int((time.perf_counter() - started) * 1000)
            return AdapterResponse(
                adapter_id=invocation.adapter_id,
                text="",
                tokens=0,
                latency_ms=latency_ms,
                raw={"error": error_detail, "status_code": e.response.status_code},
                error=f"Gemini API error ({e.response.status_code}): {error_detail}",
            )

        except Exception as e:
            logger.error("Gemini API call failed", error=str(e), model=self._model, exc_info=True)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return AdapterResponse(
                adapter_id=invocation.adapter_id,
                text="",
                tokens=0,
                latency_ms=latency_ms,
                raw={"error": str(e)},
                error=str(e),
            )

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Register the adapter
AdapterRegistry.register(GeminiAdapter.name, GeminiAdapter())
