"""Hugging Face Inference API adapter implementation."""
from __future__ import annotations

import asyncio
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
        # Use a reliable, well-known model that's publicly available
        # Default: mistralai/Mistral-7B-Instruct-v0.1 (good for instruction following)
        # Can be overridden via HUGGINGFACE_MODEL environment variable
        model_env = os.getenv("HUGGINGFACE_MODEL")
        self._model: str = model_env or "mistralai/Mistral-7B-Instruct-v0.1"
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
            # Use the standard Inference API endpoint
            base_url = "https://api-inference.huggingface.co"

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
            # Use the standard inference API endpoint format
            url = f"/models/{self._model}"
            logger.debug("Calling Hugging Face API", url=url, model=self._model)

            # Request body format for text generation
            # Send prompt as-is - the Inference API will handle model-specific formatting
            prompt_text = invocation.instructions

            request_body = {
                "inputs": prompt_text,
                "parameters": {
                    "max_new_tokens": 512,
                    "temperature": 0.7,
                    "return_full_text": False,
                    "top_p": 0.95,
                },
            }

            response = await client.post(url, json=request_body)
            
            # Handle model loading (503) - wait and retry once
            if response.status_code == 503:
                error_data = response.json()
                estimated_time = error_data.get("estimated_time", 10)
                logger.info(f"Model is loading, waiting {estimated_time}s before retry")
                # Wait for model to load
                await asyncio.sleep(min(estimated_time, 20))
                # Retry once
                response = await client.post(url, json=request_body)
            
            response.raise_for_status()
            data = response.json()

            # Hugging Face returns different formats depending on the model
            # Handle list responses (most common format)
            text = ""
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                if isinstance(item, dict):
                    text = item.get("generated_text", "")
                    # Remove the original prompt if return_full_text was False but it's still included
                    if prompt_text in text:
                        text = text.replace(prompt_text, "").strip()
                    # Remove common instruction tags if present
                    text = text.replace("[INST]", "").replace("[/INST]", "").replace("<s>", "").replace("</s>", "").strip()
                elif isinstance(item, str):
                    text = item
            elif isinstance(data, dict):
                text = data.get("generated_text", "") or data.get("text", "") or str(data)
            elif isinstance(data, str):
                text = data

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

            # Construct full URL for debugging
            base_url_str = str(client.base_url) if hasattr(client, 'base_url') and client.base_url else "https://api-inference.huggingface.co"
            full_url = f"{base_url_str}{url}"
            
            logger.error(
                "Hugging Face HTTP error",
                status_code=e.response.status_code,
                error=error_detail,
                model=self._model,
                url=full_url,
            )

            latency_ms = int((time.perf_counter() - started) * 1000)
            error_message = f"Hugging Face API error ({e.response.status_code}): {error_detail}"
            if e.response.status_code == 404:
                error_message += f". Model '{self._model}' not found at {full_url}. Try setting HUGGINGFACE_MODEL environment variable to a valid model ID like 'google/flan-t5-base'."
            
            return AdapterResponse(
                adapter_id=invocation.adapter_id,
                text="",
                tokens=0,
                latency_ms=latency_ms,
                raw={"error": error_detail, "status_code": e.response.status_code, "url": full_url, "model": self._model},
                error=error_message,
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

