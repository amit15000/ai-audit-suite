"""Hallucination scoring modules."""
from __future__ import annotations

from app.services.comparison.hallucination.fact_checking import FactCheckingScorer
from app.services.comparison.hallucination.fabricated_citations import FabricatedCitationsScorer
from app.services.comparison.hallucination.contradictory_info import ContradictoryInfoScorer
from app.services.comparison.hallucination.multi_llm_comparison import MultiLLMComparisonScorer
from app.services.comparison.hallucination.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_score,
    clamp_score,
)

__all__ = [
    "FactCheckingScorer",
    "FabricatedCitationsScorer",
    "ContradictoryInfoScorer",
    "MultiLLMComparisonScorer",
    "JUDGE_SYSTEM_PROMPT",
    "extract_json_score",
    "clamp_score",
]

