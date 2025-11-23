import time
from typing import Dict

from app.adapters.base import AdapterRegistry, BaseAdapter
from app.models import AdapterInvocation, AdapterResponse


class MockAdapter(BaseAdapter):
    name = "mock"

    def invoke(self, invocation: AdapterInvocation) -> AdapterResponse:
        started = time.perf_counter()
        synthetic = (
            f"[mock:{invocation.adapter_id}] Processed instructions: "
            f"{invocation.instructions[:128]}"
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        raw_payload: Dict[str, str] = {
            "adapter_id": invocation.adapter_id,
            "context": invocation.context or "",
        }
        return AdapterResponse(
            adapter_id=invocation.adapter_id,
            text=synthetic,
            tokens=len(synthetic.split()),
            latency_ms=latency_ms,
            raw=raw_payload,
        )


AdapterRegistry.register(MockAdapter.name, MockAdapter())

