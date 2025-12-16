"""Service for calculating explainability score and sub-scores."""
from __future__ import annotations

from app.domain.schemas import ExplainabilitySubScore
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.explainability import (
    ExplainabilityScoreScorer,
    CopiedSentencesScorer,
)


class ExplainabilityScorer:
    """Service for calculating explainability score and sub-scores."""

    def __init__(self):
        """Initialize explainability scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.explainability_score_scorer = ExplainabilityScoreScorer(self.ai_service)
        self.copied_sentences_scorer = CopiedSentencesScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> ExplainabilitySubScore:
        """Calculate the 2 explainability sub-scores.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            ExplainabilitySubScore with percentages (0-100) for:
            - explainabilityScore: Explainability Score percentage
            - copiedSentences: Copied sentences percentage
        """
        explainability_score = await self.explainability_score_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        copied_sentences = await self.copied_sentences_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return ExplainabilitySubScore(
            explainabilityScore=explainability_score,
            copiedSentences=copied_sentences,
        )

    # Legacy method names for backward compatibility
    async def calculate_explainability_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate explainability score percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Explainability score percentage (0-100)
        """
        return await self.explainability_score_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_copied_sentences(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied sentences percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Copied sentences percentage (0-100)
        """
        return await self.copied_sentences_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

