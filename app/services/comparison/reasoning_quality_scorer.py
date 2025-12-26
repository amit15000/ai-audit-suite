"""Service for calculating reasoning quality scores and sub-scores."""
from __future__ import annotations

from typing import Optional

from app.domain.schemas import (
    ReasoningQualitySubScore,
    HallucinationSubScore,
)
from app.services.comparison.reasoning_quality import (
    StepByStepReasoningScorer,
    MissingStepsScorer,
    WrongLogicScorer,
)
from app.services.llm.ai_platform_service import AIPlatformService


class ReasoningQualityScorer:
    """Service for calculating reasoning quality scores and sub-scores."""

    def __init__(self):
        """Initialize reasoning quality scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.step_by_step_reasoning_scorer = StepByStepReasoningScorer(self.ai_service)
        self.missing_steps_scorer = MissingStepsScorer(self.ai_service)
        self.wrong_logic_scorer = WrongLogicScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        hallucination_sub_score: Optional[HallucinationSubScore] = None,
    ) -> ReasoningQualitySubScore:
        """Calculate the 4 reasoning quality sub-scores.
        
        Uses LLM-based analysis for step-by-step reasoning, missing steps, and wrong logic.
        Reuses contradiction results from Hallucination Score for logical consistency.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (default: "openai")
            hallucination_sub_score: Optional HallucinationSubScore to reuse contradiction results
            
        Returns:
            ReasoningQualitySubScore with scores for:
            - stepByStepReasoning: Step-by-step reasoning quality (0-10)
            - logicalConsistency: Logical consistency (0-10, reuses contradiction score)
            - missingSteps: Missing steps detection (0-10)
            - wrongLogic: Wrong logic detection (0-10)
        """
        # Calculate independent sub-scores using LLM
        step_by_step_score = await self.step_by_step_reasoning_scorer.calculate_score(
            response, judge_platform_id
        )
        missing_steps_score = await self.missing_steps_scorer.calculate_score(
            response, judge_platform_id
        )
        wrong_logic_score = await self.wrong_logic_scorer.calculate_score(
            response, judge_platform_id
        )
        
        # Calculate logical consistency: reuse contradiction score if available
        if hallucination_sub_score is not None and hasattr(hallucination_sub_score, 'contradictoryInfoScore'):
            # Reuse the contradiction score from Hallucination Score
            logical_consistency_score = hallucination_sub_score.contradictoryInfoScore
        else:
            # Fallback: if hallucination results not available, use default neutral score
            # This ensures the score calculation doesn't fail, but ideally hallucination
            # should be calculated before reasoning quality
            logical_consistency_score = 6
        
        return ReasoningQualitySubScore(
            stepByStepReasoning=step_by_step_score,
            logicalConsistency=logical_consistency_score,
            missingSteps=missing_steps_score,
            wrongLogic=wrong_logic_score,
        )

