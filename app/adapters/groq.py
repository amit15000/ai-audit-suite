"""Groq API adapter implementation."""
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


class GroqAdapter(BaseAdapter):
    """Groq API adapter using httpx - very fast inference."""

    name = "groq"

    def __init__(self) -> None:
        super().__init__()
        self._client: httpx.AsyncClient | None = None
        self._api_key: str | None = None
        # Groq's fast models
        self._model: str = "llama-3.1-8b-instant"
        settings = get_settings()
        self._timeout = settings.adapter.timeout_seconds

    def _get_api_key(self) -> str:
        """Get Groq API key from settings or environment."""
        if self._api_key:
            return self._api_key

        settings = get_settings()
        api_key = settings.adapter.groq_api_key or os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "Groq API key is required. Set it in .env file as:\n"
                "- GROQ_API_KEY=your_key\n"
                "- ADAPTER_GROQ_API_KEY=your_key"
            )

        self._api_key = api_key
        return api_key

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of Groq HTTP client."""
        if self._client is None:
            api_key = self._get_api_key()
            base_url = "https://api.groq.com/openai/v1"

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=10.0),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                base_url=base_url,
            )
        return self._client

    async def invoke_async(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Invoke Groq API asynchronously."""
        started = time.perf_counter()
        client = self._get_client()

        try:
            url = "/chat/completions"
            logger.debug("Calling Groq API", url=url, model=self._model)

            # Groq uses OpenAI-compatible API format
            messages = []
            if invocation.system_prompt:
                messages.append({"role": "system", "content": invocation.system_prompt})
            messages.append({"role": "user", "content": invocation.instructions})
            
            request_body = {
                "model": self._model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024,
            }

            response = await client.post(url, json=request_body)
            response.raise_for_status()
            data = response.json()

            # Parse OpenAI-compatible response
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("Groq API returned no choices")

            message = choices[0].get("message", {})
            text = message.get("content", "")

            if not text:
                raise ValueError("Groq API returned empty text")

            # Calculate latency
            latency_ms = int((time.perf_counter() - started) * 1000)

            # Extract usage info
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

            raw_payload: Dict[str, Any] = {
                "adapter_id": invocation.adapter_id,
                "model": data.get("model", self._model),
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
                "response_id": data.get("id", ""),
            }

            logger.info(
                "Groq response generated",
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
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", {}).get("message", str(e))
            except Exception:
                error_detail = f"HTTP {e.response.status_code}: {e.response.text[:200]}"

            logger.error(
                "Groq HTTP error",
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
                error=f"Groq API error ({e.response.status_code}): {error_detail}",
            )

        except Exception as e:
            logger.error("Groq API call failed", error=str(e), model=self._model, exc_info=True)
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
        """Invoke Groq API with streaming."""
        started = time.perf_counter()
        client = self._get_client()

        try:
            url = "/chat/completions"
            
            messages = []
            if invocation.system_prompt:
                messages.append({"role": "system", "content": invocation.system_prompt})
            messages.append({"role": "user", "content": invocation.instructions})
            
            request_body = {
                "model": self._model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024,
                "stream": True,  # Enable streaming
            }

            async with client.stream("POST", url, json=request_body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or line.startswith("data: [DONE]"):
                        continue
                    if line.startswith("data: "):
                        import json
                        try:
                            data = json.loads(line[6:])  # Remove "data: " prefix
                            choices = data.get("choices", [])
                            if choices and len(choices) > 0:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning("Groq streaming failed, falling back to non-streaming", error=str(e))
            # Fall back to non-streaming
            response = await self.invoke_async(invocation)
            if response.error:
                raise ValueError(response.error)
            yield response.text

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Register the adapter
AdapterRegistry.register(GroqAdapter.name, GroqAdapter())

