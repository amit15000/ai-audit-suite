from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, validator


class AdapterInvocation(BaseModel):
    adapter_id: str = Field(..., description="Logical adapter identifier.")
    instructions: str = Field(..., description="Prompt or task specification.")
    context: Optional[str] = Field(
        None, description="Optional context blob provided by caller."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary caller-provided metadata."
    )


class AuditRequest(BaseModel):
    job_id: str = Field(..., description="Deterministic audit job identifier.")
    prompt: str = Field(..., description="Primary task description.")
    adapters: List[AdapterInvocation] = Field(
        ..., min_items=1, description="List of adapter invocations to execute."
    )
    pii_allowed: bool = Field(
        False, description="Whether PII is permitted for this audit."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata for downstream systems."
    )


class AdapterResponse(BaseModel):
    text: str
    tokens: int
    latency_ms: int
    raw: Dict[str, Any]
    adapter_id: str
    error: Optional[str] = None


class SafetyFinding(BaseModel):
    category: Literal["harmful_content", "pii_violation", "other"]
    details: str
    replaced_text: Optional[str] = None


class SafetyResult(BaseModel):
    adapter_id: str
    sanitized_text: str
    findings: List[SafetyFinding] = Field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)


class JudgmentScores(BaseModel):
    accuracy: int
    completeness: int
    clarity: int
    reasoning: int
    safety: int
    hallucination_risk: int

    @validator("*")
    def _in_range(cls, value: int) -> int:
        if not 0 <= value <= 10:
            raise ValueError("Scores must be between 0 and 10 inclusive.")
        return value


class AdapterAuditArtifact(BaseModel):
    adapter_id: str
    sanitized_text: str
    findings: List[SafetyFinding]
    scores: JudgmentScores
    citations: List[str] = Field(default_factory=list)


class ConsensusContributor(BaseModel):
    adapter_id: str
    evidence: str


class ConsensusOutput(BaseModel):
    summary: str
    contributors: List[ConsensusContributor]
    citations: List[str]


class AuditResponse(BaseModel):
    job_id: str
    status: Literal["completed", "failed"]
    artifacts: List[AdapterAuditArtifact]
    consensus: ConsensusOutput
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

