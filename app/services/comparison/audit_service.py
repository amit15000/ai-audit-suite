from __future__ import annotations

import asyncio
import logging
from typing import List

import structlog

from app.adapters.base import AdapterRegistry
from app.domain.schemas import (
    AdapterAuditArtifact,
    AdapterResponse,
    AuditRequest,
    AuditResponse,
)
from app.services.judgment.consensus import ConsensusEngine
from app.services.judgment.judge import JudgeEngine
from app.services.core.metrics import AUDIT_LATENCY_SECONDS, AUDIT_REQUESTS_TOTAL, JUDGE_FAILURES_TOTAL
from app.services.core.safety_checker import SafetyChecker
from app.services.core.storage import ObjectStoreClient, RelationalStore

logger = structlog.get_logger(__name__)


class AuditService:
    def __init__(self) -> None:
        self._safety = SafetyChecker()
        self._judge = JudgeEngine()
        self._consensus = ConsensusEngine()
        self._object_store = ObjectStoreClient()
        self._relational_store = RelationalStore()

    async def execute_async(self, request: AuditRequest) -> AuditResponse:
        """Async execution of audit request."""
        AUDIT_REQUESTS_TOTAL.inc()

        with AUDIT_LATENCY_SECONDS.time():
            adapter_outputs = await self._fan_out_async(request)
            artifacts = self._process_outputs(request, adapter_outputs)
            consensus = self._consensus.build(artifacts)

            response = AuditResponse(
                job_id=request.job_id,
                status="completed",
                artifacts=artifacts,
                consensus=consensus,
            )

            self._persist_audit(response)
            return response

    def execute(self, request: AuditRequest) -> AuditResponse:
        """Sync wrapper for async execution."""
        return asyncio.run(self.execute_async(request))

    async def _fan_out_async(self, request: AuditRequest) -> List[AdapterResponse]:
        """Execute all adapters in parallel."""
        from app.domain.schemas import AdapterInvocation
        
        # Create tasks for all adapters
        tasks = []
        for adapter_id in request.adapters:
            adapter = AdapterRegistry.get(adapter_id)
            if not adapter:
                raise ValueError(f"Adapter {adapter_id} not registered.")
            
            logger.info("adapter.invoke", adapter=adapter_id)
            invocation = AdapterInvocation(
                adapter_id=adapter_id,
                instructions=request.prompt
            )
            # Create async task
            task = adapter.run_async(invocation)
            tasks.append(task)
        
        # Execute all adapters in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        adapter_outputs: List[AdapterResponse] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("adapter.error", adapter=request.adapters[i], error=str(result))
                # Create error response
                adapter_outputs.append(AdapterResponse(
                    adapter_id=request.adapters[i],
                    text="",
                    tokens=0,
                    latency_ms=0,
                    raw={"error": str(result)},
                    error=str(result),
                ))
            elif isinstance(result, AdapterResponse):
                adapter_outputs.append(result)
            else:
                # Fallback for unexpected types
                logger.error("adapter.unexpected_result", adapter=request.adapters[i], result_type=type(result).__name__)
                adapter_outputs.append(AdapterResponse(
                    adapter_id=request.adapters[i],
                    text="",
                    tokens=0,
                    latency_ms=0,
                    raw={"error": "Unexpected result type"},
                    error="Unexpected result type",
                ))
        
        return adapter_outputs

    def _process_outputs(
        self, request: AuditRequest, outputs: List[AdapterResponse]
    ) -> List[AdapterAuditArtifact]:
        artifacts: List[AdapterAuditArtifact] = []
        for output in outputs:
            safety = self._safety.sanitize(
                adapter_id=output.adapter_id,
                text=output.text,
                pii_allowed=request.pii_allowed,
            )

            judge_result = self._judge.score(safety.sanitized_text)
            if judge_result.fallback_applied:
                JUDGE_FAILURES_TOTAL.inc()

            artifact = AdapterAuditArtifact(
                adapter_id=output.adapter_id,
                sanitized_text=safety.sanitized_text,
                findings=safety.findings,
                scores=judge_result.payload,
                citations=[f"artifact:{output.adapter_id}"],
            )
            self._object_store.persist(
                key=f"{request.job_id}-{output.adapter_id}",
                payload={
                    "raw": output.raw,
                    "sanitized_text": safety.sanitized_text,
                    "findings": [finding.dict() for finding in safety.findings],
                    "scores": judge_result.payload.dict(),
                },
            )
            artifacts.append(artifact)
        return artifacts

    def _persist_audit(self, response: AuditResponse) -> None:
        payload = response.model_dump()
        self._relational_store.persist_event(job_id=response.job_id, payload=payload)

