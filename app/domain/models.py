"""SQLAlchemy ORM models for database tables."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AuditEvent(Base):
    """ORM model for audit events table."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AuditEvent(id={self.id}, job_id={self.job_id}, created_at={self.created_at})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LLMResponse(Base):
    """ORM model for storing LLM API responses with metrics."""

    __tablename__ = "llm_responses"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, nullable=False, index=True, comment="Groups responses from the same request")
    provider = Column(String, nullable=False, index=True, comment="LLM provider/adapter ID (e.g., 'openai', 'gemini')")
    prompt = Column(Text, nullable=False, comment="The prompt sent to the LLM")
    raw_response = Column(Text, nullable=False, comment="Raw response text from the LLM")
    latency_ms = Column(Integer, nullable=False, comment="Response latency in milliseconds")
    prompt_tokens = Column(Integer, nullable=True, comment="Number of tokens in the prompt")
    completion_tokens = Column(Integer, nullable=True, comment="Number of tokens in the completion")
    total_tokens = Column(Integer, nullable=False, comment="Total tokens used")
    raw_metadata = Column(JSON, nullable=True, comment="Additional raw metadata from the API response")
    error = Column(Text, nullable=True, comment="Error message if the request failed")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<LLMResponse(id={self.id}, request_id={self.request_id}, "
            f"provider={self.provider}, latency_ms={self.latency_ms}, "
            f"total_tokens={self.total_tokens})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "provider": self.provider,
            "prompt": self.prompt,
            "raw_response": self.raw_response,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "raw_metadata": self.raw_metadata,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class User(Base):
    """ORM model for users table."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    comparisons = relationship("Comparison", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ComparisonStatus(str, Enum):
    """Comparison status enum."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Comparison(Base):
    """ORM model for comparisons table."""

    __tablename__ = "comparisons"

    id = Column(String, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    judge_platform = Column(String, nullable=False)
    selected_platforms = Column(JSON, nullable=False)  # List of platform IDs
    status = Column(String, default=ComparisonStatus.QUEUED.value, nullable=False, index=True)
    progress = Column(Integer, default=0, nullable=False)
    results = Column(JSON, nullable=True)  # Full results JSON
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="comparisons")

    def __repr__(self) -> str:
        return f"<Comparison(id={self.id}, status={self.status}, progress={self.progress})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "user_id": self.user_id,
            "prompt": self.prompt,
            "judge_platform": self.judge_platform,
            "selected_platforms": self.selected_platforms,
            "status": self.status,
            "progress": self.progress,
            "results": self.results,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Embedding(Base):
    """ORM model for storing embeddings of LLM responses."""

    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, nullable=False, index=True, comment="Request ID to group embeddings")
    provider = Column(String, nullable=False, index=True, comment="LLM provider/adapter ID")
    text = Column(Text, nullable=False, comment="The text that was embedded")
    embedding_vector = Column(JSON, nullable=False, comment="Embedding vector as JSON array")
    model_name = Column(String, nullable=False, comment="Embedding model used")
    embedding_dimension = Column(Integer, nullable=False, comment="Dimension of the embedding vector")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Embedding(id={self.id}, request_id={self.request_id}, "
            f"provider={self.provider}, dimension={self.embedding_dimension})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "provider": self.provider,
            "text": self.text,
            "embedding_vector": self.embedding_vector,
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dimension,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SimilarityAnalysis(Base):
    """ORM model for storing similarity analysis results."""

    __tablename__ = "similarity_analyses"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, nullable=False, index=True, comment="Request ID to group analyses")
    similarity_matrix = Column(JSON, nullable=False, comment="Full similarity matrix as nested dict")
    consensus_scores = Column(JSON, nullable=False, comment="Consensus scores for each provider")
    outliers = Column(JSON, nullable=True, comment="List of outlier provider IDs")
    outlier_threshold = Column(String, nullable=True, comment="Threshold used for outlier detection")
    statistics = Column(JSON, nullable=True, comment="Statistical summary of consensus scores")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<SimilarityAnalysis(id={self.id}, request_id={self.request_id}, "
            f"outliers_count={len(self.outliers) if self.outliers else 0})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "similarity_matrix": self.similarity_matrix,
            "consensus_scores": self.consensus_scores,
            "outliers": self.outliers,
            "outlier_threshold": self.outlier_threshold,
            "statistics": self.statistics,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LLMProvider(Base):
    """ORM model for LLM providers in the promotion platform."""

    __tablename__ = "llm_providers"

    id = Column(String, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    provider_name = Column(String, nullable=False, unique=True, index=True)
    api_endpoint = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    is_approved = Column(Boolean, default=False, nullable=False, index=True)
    is_promoted = Column(Boolean, default=False, nullable=False, index=True)
    promotion_tier = Column(String, default="free", nullable=False)  # free, basic, premium
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<LLMProvider(id={self.id}, provider_name={self.provider_name}, is_approved={self.is_approved})>"


class UserPreference(Base):
    """ORM model for user output preferences."""

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    comparison_id = Column(String, ForeignKey("comparisons.id"), nullable=True, index=True)
    preferred_provider = Column(String, nullable=False)
    preference_reason = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<UserPreference(id={self.id}, user_id={self.user_id}, preferred_provider={self.preferred_provider})>"


class PromotionPayment(Base):
    """ORM model for LLM promotion payments."""

    __tablename__ = "promotion_payments"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(String, ForeignKey("llm_providers.id"), nullable=False, index=True)
    tier = Column(String, nullable=False)  # basic, premium
    amount = Column(String, nullable=False)
    payment_status = Column(String, default="pending", nullable=False)  # pending, completed, failed
    payment_method = Column(String, nullable=True)
    transaction_id = Column(String, nullable=True, unique=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<PromotionPayment(id={self.id}, provider_id={self.provider_id}, tier={self.tier}, status={self.payment_status})>"


class ChatbotEvaluation(Base):
    """ORM model for chatbot evaluation jobs."""

    __tablename__ = "chatbot_evaluations"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    chatbot_url = Column(String, nullable=True)
    chatbot_api_key = Column(String, nullable=True)
    status = Column(String, default="pending", nullable=False, index=True)  # pending, processing, completed, failed
    questions = Column(JSON, nullable=False)  # List of original questions
    results = Column(JSON, nullable=True)  # Evaluation results
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ChatbotEvaluation(id={self.id}, status={self.status})>"


class QuestionVariation(Base):
    """ORM model for question variations in chatbot evaluation."""

    __tablename__ = "question_variations"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(String, ForeignKey("chatbot_evaluations.id"), nullable=False, index=True)
    original_question = Column(Text, nullable=False)
    variation_text = Column(Text, nullable=False)
    variation_type = Column(String, nullable=True)  # typo, paraphrase, rephrase, etc.
    correct_answer = Column(Text, nullable=True)  # Generated correct answer
    chatbot_response = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    similarity_score = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<QuestionVariation(id={self.id}, evaluation_id={self.evaluation_id})>"

