"""OpenAI adapter implementation."""
from __future__ import annotations

import os
import time
from typing import Any, Dict

from openai import OpenAI

from app.adapters.base import AdapterRegistry, BaseAdapter
from app.core.config import get_settings
from app.domain.schemas import AdapterInvocation, AdapterResponse


class OpenAIAdapter(BaseAdapter):
    name = "openai"

    def __init__(self) -> None:
        super().__init__()
        self._client = None
        settings = get_settings()
        self._timeout = settings.adapter.timeout_seconds

    def _get_client(self) -> OpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            # Try to get from settings first, then fall back to environment variable
            settings = get_settings()
            api_key = settings.adapter.openai_api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required. Set it in .env file as OPENAI_API_KEY=your_key "
                    "or ADAPTER_OPENAI_API_KEY=your_key"
                )
            self._client = OpenAI(api_key=api_key)
        return self._client

    async def invoke_async(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Invoke OpenAI API asynchronously."""
        import asyncio
        
        started = time.perf_counter()
        client = self._get_client()
        
        try:
            # Run the synchronous API call in a thread pool
            loop = asyncio.get_event_loop()
            
            messages = []
            if invocation.system_prompt:
                messages.append({"role": "system", "content": invocation.system_prompt})
            messages.append({"role": "user", "content": invocation.instructions})
            
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    timeout=self._timeout,
                )
            )
            
            text = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else 0
            latency_ms = int((time.perf_counter() - started) * 1000)
            
            raw_payload: Dict[str, Any] = {
                "adapter_id": invocation.adapter_id,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": tokens,
                },
                "response_id": response.id,
            }
            
            return AdapterResponse(
                adapter_id=invocation.adapter_id,
                text=text,
                tokens=tokens,
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
AdapterRegistry.register(OpenAIAdapter.name, OpenAIAdapter())

