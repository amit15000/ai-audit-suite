from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import AdapterError
from app.domain.schemas import AdapterInvocation, AdapterResponse


@dataclass
class AdapterContext:
    invocation: AdapterInvocation
    metadata: Dict[str, Any]


class BaseAdapter(ABC):
    name: str

    def __init__(self) -> None:
        settings = get_settings()
        self._max_retries = settings.adapter.max_retries

    async def run_async(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Async wrapper with retry logic."""
        try:
            return await self.invoke_async(invocation)
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(str(exc)) from exc

    @abstractmethod
    async def invoke_async(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Async method to invoke the adapter."""
        ...
    
    async def invoke_streaming(self, invocation: AdapterInvocation):
        """Optional streaming method - override in adapters that support it.
        
        Default implementation falls back to invoke_async and simulates streaming.
        """
        response = await self.invoke_async(invocation)
        if response.error:
            raise AdapterError(response.error)
        
        # Simulate streaming by yielding the full text
        yield response.text

    # Legacy sync support (for backward compatibility)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    def run(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Sync wrapper - runs async method in event loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.invoke_async(invocation))
                    return future.result()
            else:
                return loop.run_until_complete(self.invoke_async(invocation))
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(str(exc)) from exc

    def invoke(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Sync invoke - delegates to async."""
        return self.run(invocation)


class AdapterRegistry:
    _registry: Dict[str, BaseAdapter] = {}

    @classmethod
    def register(cls, name: str, adapter: BaseAdapter) -> None:
        cls._registry[name] = adapter

    @classmethod
    def get(cls, name: str) -> Optional[BaseAdapter]:
        return cls._registry.get(name)

    @classmethod
    def all(cls) -> Dict[str, BaseAdapter]:
        return cls._registry

