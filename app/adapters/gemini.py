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

    def _create_client(self) -> httpx.AsyncClient:
        """Create a new HTTP client for streaming requests.
        
        This creates a fresh client instance for each streaming request to avoid
        blocking issues with shared client instances in parallel execution.
        """
        api_key = self._get_api_key()
        # Use v1beta endpoint as per official documentation
        base_url = "https://generativelanguage.googleapis.com/v1beta"
        
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout, connect=10.0),
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            base_url=base_url,
        )

    async def invoke_async(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Invoke Gemini API asynchronously using httpx."""
        started = time.perf_counter()
        client = self._get_client()

        try:
            url = f"/models/{self._model}:generateContent"
            logger.debug("Calling Gemini API", url=url, model=self._model)

            # Request body format as per official documentation
            request_body: Dict[str, Any] = {
                "contents": [
                    {
                        "parts": [
                            {"text": invocation.instructions}
                        ]
                    }
                ]
            }
            # Add system instruction if provided
            if invocation.system_prompt:
                request_body["systemInstruction"] = {
                    "parts": [{"text": invocation.system_prompt}]
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

    async def invoke_streaming(self, invocation: AdapterInvocation):
        """Invoke Gemini API with streaming.
        
        According to Gemini API documentation:
        - Requires `alt=sse` query parameter for Server-Sent Events format
        - Response lines are prefixed with `data: ` followed by JSON
        - Each chunk contains delta text (new text only), not full accumulated text
        """
        # Create a fresh client for each streaming request to avoid blocking
        # Yield control immediately after client creation to allow parallel execution
        import asyncio
        client = self._create_client()
        await asyncio.sleep(0)

        try:
            # Add alt=sse query parameter for SSE streaming format
            url = f"/models/{self._model}:streamGenerateContent?alt=sse"
            logger.debug("Calling Gemini API with streaming", url=url, model=self._model)

            request_body: Dict[str, Any] = {
                "contents": [
                    {
                        "parts": [
                            {"text": invocation.instructions}
                        ]
                    }
                ]
            }
            if invocation.system_prompt:
                request_body["systemInstruction"] = {
                    "parts": [{"text": invocation.system_prompt}]
                }

            chunk_count = 0
            logger.info("Gemini streaming: starting HTTP stream", url=url, model=self._model, prompt_length=len(invocation.instructions))
            
            # Use client as context manager to ensure it's properly closed
            async with client:
                # Start the stream - stream will be automatically closed by context manager
                async with client.stream("POST", url, json=request_body) as response:
                    logger.info("Gemini streaming: HTTP stream context entered", status_code=response.status_code)
                    response.raise_for_status()
                    logger.info("Gemini streaming: HTTP stream opened successfully", status_code=response.status_code)
                    # Yield control to allow other tasks to proceed in parallel
                    await asyncio.sleep(0)
                    
                    # Read from stream line by line
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Skip non-data lines (like event types, comments, etc.)
                        if not line.startswith("data: "):
                            continue
                        
                        # Extract JSON from "data: {...}" format
                        json_str = line[6:]  # Remove "data: " prefix
                        if json_str == "[DONE]":
                            # End of stream marker
                            logger.debug("Gemini streaming: received [DONE] marker")
                            break
                        
                        import json
                        try:
                            data = json.loads(json_str)
                            candidates = data.get("candidates", [])
                            if not candidates or len(candidates) == 0:
                                continue
                            
                            candidate = candidates[0]
                            content = candidate.get("content", {})
                            if not content:
                                continue
                            
                            parts = content.get("parts", [])
                            if not parts or len(parts) == 0:
                                continue
                            
                            # According to Gemini API docs, each chunk contains delta text (new text only)
                            current_text = parts[0].get("text", "")
                            if current_text:
                                chunk_count += 1
                                if chunk_count == 1:
                                    logger.info("Gemini streaming: first chunk received", chunk_preview=current_text[:50])
                                yield current_text
                                
                        except json.JSONDecodeError as e:
                            logger.debug("Gemini streaming: failed to parse JSON", json_str=json_str[:200], error=str(e))
                            continue
                        except Exception as e:
                            logger.warning("Gemini streaming: error processing chunk", error=str(e), exc_info=True)
                            continue
                
                # Log summary
                logger.info("Gemini streaming: completed", chunk_count=chunk_count, url=url, model=self._model)
                if chunk_count == 0:
                    logger.warning("Gemini streaming: no text chunks received - check API response format", url=url, model=self._model)
        except Exception as e:
            logger.error("Gemini streaming failed, falling back to non-streaming", error=str(e), exc_info=True)
            # Fall back to non-streaming
            try:
                response = await self.invoke_async(invocation)
                if response.error:
                    raise ValueError(response.error)
                # Yield the full response as a single chunk
                if response.text:
                    yield response.text
            except Exception as fallback_error:
                logger.error("Gemini fallback to non-streaming also failed", error=str(fallback_error), exc_info=True)
                raise

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
        self._client = None


# Register the adapter
AdapterRegistry.register(GeminiAdapter.name, GeminiAdapter())
