"""Services package - organized by domain."""
from __future__ import annotations

# Re-export all services for backward compatibility and convenience
from app.services.comparison import (
    AuditScorer,
    AuditService,
    create_comparison,
    get_comparison_results,
    get_comparison_status,
    process_comparison,
)
from app.services.core import (
    AUDIT_LATENCY_SECONDS,
    AUDIT_REQUESTS_TOTAL,
    JUDGE_FAILURES_TOTAL,
    ObjectStoreClient,
    RelationalStore,
    SafetyChecker,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.services.embedding import (
    ConsensusScorer,
    EmbeddingService,
    OutlierDetector,
    SimilarityProcessor,
    SimilarityService,
)
from app.services.judgment import ConsensusEngine, JudgeEngine, JudgeResult
from app.services.llm import AIPlatformService, MultiLLMCollector, MultiLLMCollectionResult

__all__ = [
    # Comparison services
    "AuditScorer",
    "AuditService",
    "create_comparison",
    "get_comparison_results",
    "get_comparison_status",
    "process_comparison",
    # Core services
    "AUDIT_LATENCY_SECONDS",
    "AUDIT_REQUESTS_TOTAL",
    "JUDGE_FAILURES_TOTAL",
    "ObjectStoreClient",
    "RelationalStore",
    "SafetyChecker",
    "authenticate_user",
    "create_access_token",
    "create_refresh_token",
    "get_password_hash",
    "verify_password",
    # Embedding services
    "ConsensusScorer",
    "EmbeddingService",
    "OutlierDetector",
    "SimilarityProcessor",
    "SimilarityService",
    # Judgment services
    "ConsensusEngine",
    "JudgeEngine",
    "JudgeResult",
    # LLM services
    "AIPlatformService",
    "MultiLLMCollector",
    "MultiLLMCollectionResult",
]

