"""Hugging Face Inference API adapter implementation."""
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


class HuggingFaceAdapter(BaseAdapter):
    """Hugging Face Inference API adapter using httpx."""

    name = "huggingface"

    def __init__(self) -> None:
        super().__init__()
        self._client: httpx.AsyncClient | None = None
        self._api_key: str | None = None
        # Default to a popular free model
        self._model: str = "mistralai/Mistral-7B-Instruct-v0.2"
        settings = get_settings()
        self._timeout = settings.adapter.timeout_seconds

    def _get_api_key(self) -> str | None:
        """Get Hugging Face API key (optional for public models)."""
        if self._api_key:
            return self._api_key

        settings = get_settings()
        api_key = (
            settings.adapter.huggingface_api_key
            or os.getenv("HUGGINGFACE_API_KEY")
            or os.getenv("HF_API_KEY")
        )

        self._api_key = api_key
        return api_key

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of Hugging Face HTTP client."""
        if self._client is None:
            api_key = self._get_api_key()
            # Updated to use the new router endpoint (old api-inference endpoint is deprecated)
            base_url = "https://router.huggingface.co"

            headers = {
                "Content-Type": "application/json",
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=10.0),
                headers=headers,
                base_url=base_url,
            )
        return self._client

    async def invoke_async(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Invoke Hugging Face Inference API asynchronously."""
        started = time.perf_counter()
        client = self._get_client()

        try:
            url = f"/models/{self._model}"
            logger.debug("Calling Hugging Face API", url=url, model=self._model)

            # Request body format for text generation
            request_body = {
                "inputs": invocation.instructions,
                "parameters": {
                    "max_new_tokens": 512,
                    "temperature": 0.7,
                    "return_full_text": False,
                },
            }

            response = await client.post(url, json=request_body)
            response.raise_for_status()
            data = response.json()

            # Hugging Face returns different formats depending on the model
            # Handle both list and dict responses
            if isinstance(data, list) and len(data) > 0:
                text = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                text = data.get("generated_text", "") or data.get("text", "")
            else:
                text = str(data)

            if not text:
                raise ValueError("Hugging Face API returned empty response")

            # Calculate latency
            latency_ms = int((time.perf_counter() - started) * 1000)

            # Estimate tokens
            estimated_tokens = len(text.split()) * 1.3

            raw_payload: Dict[str, Any] = {
                "adapter_id": invocation.adapter_id,
                "model": self._model,
                "estimated_tokens": int(estimated_tokens),
                "response_data": data,
            }

            logger.info(
                "Hugging Face response generated",
                model=self._model,
                prompt_length=len(invocation.instructions),
                response_length=len(text),
                latency_ms=latency_ms,
            )

            return AdapterResponse(
                adapter_id=invocation.adapter_id,
                text=text,
                tokens=int(estimated_tokens),
                latency_ms=latency_ms,
                raw=raw_payload,
            )

        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", str(e))
            except Exception:
                error_detail = f"HTTP {e.response.status_code}: {e.response.text[:200]}"

            logger.error(
                "Hugging Face HTTP error",
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
                error=f"Hugging Face API error ({e.response.status_code}): {error_detail}",
            )

        except Exception as e:
            logger.error("Hugging Face API call failed", error=str(e), model=self._model, exc_info=True)
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
AdapterRegistry.register(HuggingFaceAdapter.name, HuggingFaceAdapter())

