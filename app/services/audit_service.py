from __future__ import annotations

import logging
from typing import List

import structlog

from app.adapters.base import AdapterRegistry
from app.models import (
    AdapterAuditArtifact,
    AdapterResponse,
    AuditRequest,
    AuditResponse,
)
from app.services.consensus import ConsensusEngine
from app.services.judge import JudgeEngine
from app.services.metrics import AUDIT_LATENCY_SECONDS, AUDIT_REQUESTS_TOTAL, JUDGE_FAILURES_TOTAL
from app.services.safety_checker import SafetyChecker
from app.services.storage import ObjectStoreClient, RelationalStore

logger = structlog.get_logger(__name__)


class AuditService:
    def __init__(self) -> None:
        self._safety = SafetyChecker()
        self._judge = JudgeEngine()
        self._consensus = ConsensusEngine()
        self._object_store = ObjectStoreClient()
        self._relational_store = RelationalStore()

    def execute(self, request: AuditRequest) -> AuditResponse:
        AUDIT_REQUESTS_TOTAL.inc()

        with AUDIT_LATENCY_SECONDS.time():
            adapter_outputs = self._fan_out(request)
            artifacts = self._process_outputs(request, adapter_outputs)
            consensus = self._consensus.build(artifacts)

            response = AuditResponse(
                job_id=request.job_id,
                status="completed",
                artifacts=artifacts,
                consensus=consensus,
                metadata=request.metadata,
            )

            self._persist_audit(response)
            return response

    def _fan_out(self, request: AuditRequest) -> List[AdapterResponse]:
        results: List[AdapterResponse] = []
        for invocation in request.adapters:
            adapter = AdapterRegistry.get(invocation.adapter_id)
            if not adapter:
                raise ValueError(f"Adapter {invocation.adapter_id} not registered.")
            logger.info("adapter.invoke", adapter=invocation.adapter_id)
            result = adapter.run(invocation)
            results.append(result)
        return results

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

