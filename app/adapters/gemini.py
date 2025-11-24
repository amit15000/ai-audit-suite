"""Google Gemini adapter implementation."""
from __future__ import annotations

import os
import time
from typing import Any, Dict

import google.generativeai as genai

from app.adapters.base import AdapterRegistry, BaseAdapter
from app.core.config import get_settings
from app.domain.schemas import AdapterInvocation, AdapterResponse


class GeminiAdapter(BaseAdapter):
    name = "gemini"

    def __init__(self) -> None:
        super().__init__()
        self._client = None
        settings = get_settings()
        self._timeout = settings.adapter.timeout_seconds

    def _get_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None:
            # Try to get from settings first, then fall back to environment variable
            settings = get_settings()
            api_key = settings.adapter.google_api_key or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError(
                    "GOOGLE_API_KEY is required. Set it in .env file as GOOGLE_API_KEY=your_key "
                    "or ADAPTER_GOOGLE_API_KEY=your_key"
                )
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel("gemini-1.5-flash")
        return self._client

    async def invoke_async(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Invoke Gemini API asynchronously."""
        started = time.perf_counter()
        client = self._get_client()
        
        try:
            # Run the synchronous API call in a thread pool
            import asyncio
            loop = asyncio.get_event_loop()
            
            response = await loop.run_in_executor(
                None,
                lambda: client.generate_content(invocation.instructions)
            )
            
            text = response.text if response.text else ""
            # Estimate tokens (Gemini doesn't provide exact token counts in free tier)
            estimated_tokens = len(text.split()) * 1.3  # Rough estimate
            latency_ms = int((time.perf_counter() - started) * 1000)
            
            raw_payload: Dict[str, Any] = {
                "adapter_id": invocation.adapter_id,
                "model": "gemini-1.5-flash",
                "estimated_tokens": int(estimated_tokens),
                "response_id": getattr(response, "candidates", [{}])[0].get("finish_reason", "unknown") if hasattr(response, "candidates") else "unknown",
            }
            
            return AdapterResponse(
                adapter_id=invocation.adapter_id,
                text=text,
                tokens=int(estimated_tokens),
                latency_ms=latency_ms,
                raw=raw_payload,
            )
        except Exception as e:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return AdapterResponse(
                adapter_id=invocation.adapter_id,
                text="",
                tokens=0,
                latency_ms=latency_ms,
                raw={"error": str(e)},
                error=str(e),
            )


# Register the adapter
AdapterRegistry.register(GeminiAdapter.name, GeminiAdapter())

