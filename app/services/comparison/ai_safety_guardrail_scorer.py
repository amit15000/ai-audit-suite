"""Service for calculating AI safety guardrail test scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import AISafetyGuardrailSubScore
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.ai_safety_guardrail import SafetyScoreScorer


class AISafetyGuardrailScorer:
    """Service for calculating AI safety guardrail test scores and sub-scores."""

    def __init__(self):
        """Initialize AI safety guardrail scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.safety_score_scorer = SafetyScoreScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> AISafetyGuardrailSubScore:
        """Calculate the AI safety guardrail sub-score.
        
        Measures how well safety guardrails are functioning.
        Higher percentage = better safety guardrail performance.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            AISafetyGuardrailSubScore with:
            - safetyScore: Safety score percentage (0-100)
        """
        safety_score = await self.safety_score_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return AISafetyGuardrailSubScore(
            safetyScore=safety_score,
        )

    # Legacy method name for backward compatibility
    async def calculate_safety_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate safety score percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Safety score percentage (0-100)
        """
        return await self.safety_score_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

