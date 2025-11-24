import asyncio
import time
from typing import Dict

from app.adapters.base import AdapterRegistry, BaseAdapter
from app.domain.schemas import AdapterInvocation, AdapterResponse


class MockAdapter(BaseAdapter):
    name = "mock"

    async def invoke_async(self, invocation: AdapterInvocation) -> AdapterResponse:
        """Mock adapter with simulated latency."""
        started = time.perf_counter()
        # Simulate some processing time
        await asyncio.sleep(0.1)
        
        synthetic = (
            f"[mock:{invocation.adapter_id}] Processed prompt: "
            f"{invocation.instructions[:128]}"
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        raw_payload: Dict[str, str] = {
            "adapter_id": invocation.adapter_id,
            "instructions": invocation.instructions,
        }
        return AdapterResponse(
            adapter_id=invocation.adapter_id,
            text=synthetic,
            tokens=len(synthetic.split()),
            latency_ms=latency_ms,
            raw=raw_payload,
        )


AdapterRegistry.register(MockAdapter.name, MockAdapter())

