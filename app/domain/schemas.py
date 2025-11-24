"""Pydantic schemas for API request/response models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, validator


class AdapterInvocation(BaseModel):
    """Schema for adapter invocation request."""

    adapter_id: str = Field(..., description="Logical adapter identifier.")
    instructions: str = Field(..., description="Prompt or task specification.")


class AuditRequest(BaseModel):
    """Schema for audit request."""

    job_id: str = Field(..., description="Deterministic audit job identifier.")
    prompt: str = Field(..., description="Prompt to be analyzed and scored.")
    adapters: List[str] = Field(  # pyright: ignore[reportCallIssue]
        ..., min_items=1, description="List of adapter IDs to analyze the prompt."
    )
    pii_allowed: bool = Field(
        False, description="Whether PII is permitted for this audit."
    )


class AdapterResponse(BaseModel):
    """Schema for adapter response."""

    text: str
    tokens: int
    latency_ms: int
    raw: Dict[str, Any]
    adapter_id: str
    error: Optional[str] = None


class SafetyFinding(BaseModel):
    """Schema for safety finding."""

    category: Literal["harmful_content", "pii_violation", "other"]
    details: str
    replaced_text: Optional[str] = None


class SafetyResult(BaseModel):
    """Schema for safety check result."""

    adapter_id: str
    sanitized_text: str
    findings: List[SafetyFinding] = Field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)


class JudgmentScores(BaseModel):
    """Schema for judgment scores."""

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
    """Schema for adapter audit artifact."""

    adapter_id: str
    sanitized_text: str
    findings: List[SafetyFinding]
    scores: JudgmentScores
    citations: List[str] = Field(default_factory=list)


class ConsensusContributor(BaseModel):
    """Schema for consensus contributor."""

    adapter_id: str
    evidence: str


class ConsensusOutput(BaseModel):
    """Schema for consensus output."""

    summary: str
    contributors: List[ConsensusContributor]
    citations: List[str]


class AuditResponse(BaseModel):
    """Schema for audit response."""

    job_id: str
    status: Literal["completed", "failed"]
    artifacts: List[AdapterAuditArtifact]
    consensus: ConsensusOutput
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MultiLLMRequest(BaseModel):
    """Request model for multi-LLM response collection endpoint.
    
    Note: request_id is auto-generated and not required in the request.
    It will be returned in the response for tracking purposes.
    """

    prompt: str = Field(
        default="What is AI",
        description="The prompt to send to all LLM providers"
    )
    adapter_ids: List[str] = Field(
        default=["openai", "gemini"],
        min_length=1,
        description="List of adapter/provider IDs to query. All adapters run simultaneously in parallel.",
    )


class MultiLLMResponseItem(BaseModel):
    """Individual LLM response item in the multi-LLM response."""

    adapter_id: str = Field(..., description="The adapter/provider ID")
    text: str = Field(..., description="The response text from the LLM")
    tokens: int = Field(..., description="Total tokens used")
    latency_ms: int = Field(..., description="Response latency in milliseconds")
    prompt_tokens: Optional[int] = Field(None, description="Number of tokens in the prompt")
    completion_tokens: Optional[int] = Field(None, description="Number of tokens in the completion")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional raw metadata")
    error: Optional[str] = Field(None, description="Error message if the request failed")
    success: bool = Field(..., description="Whether the request was successful")


class MultiLLMResponse(BaseModel):
    """Response model for multi-LLM response collection endpoint."""

    request_id: str = Field(..., description="Request ID used to group responses")
    prompt: str = Field(..., description="The prompt that was sent")
    responses: List[MultiLLMResponseItem] = Field(..., description="List of responses from each LLM")
    total_responses: int = Field(..., description="Total number of responses")
    successful_responses: int = Field(..., description="Number of successful responses")
    failed_responses: int = Field(..., description="Number of failed responses")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the request")

