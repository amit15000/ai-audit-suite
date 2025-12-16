"""Multi-LLM consensus scoring modules."""
from __future__ import annotations

from app.services.comparison.multi_llm_consensus.four_model_agree import FourModelAgreeScorer
from app.services.comparison.multi_llm_consensus.two_model_disagree import TwoModelDisagreeScorer

__all__ = [
    "FourModelAgreeScorer",
    "TwoModelDisagreeScorer",
]

