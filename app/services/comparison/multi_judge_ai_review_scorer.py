"""Service for calculating multi-judge AI review scores and sub-scores."""
from __future__ import annotations

from typing import Dict

from app.domain.schemas import MultiJudgeAIReviewSubScore
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.multi_judge_ai_review import (
    ModelVotingScorer,
    ModelScoringScorer,
    ModelCritiquesScorer,
)


class MultiJudgeAIReviewScorer:
    """Service for calculating multi-judge AI review scores and sub-scores."""

    def __init__(self):
        """Initialize multi-judge AI review scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.model_voting_scorer = ModelVotingScorer(self.ai_service)
        self.model_scoring_scorer = ModelScoringScorer(self.ai_service)
        self.model_critiques_scorer = ModelCritiquesScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        all_responses: Dict[str, str],
        judge_platform_id: str = "",
        use_llm: bool = False,
    ) -> MultiJudgeAIReviewSubScore:
        """Calculate the 3 multi-judge AI review sub-scores.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            MultiJudgeAIReviewSubScore with percentages (0-100) for:
            - modelVoting: Model voting percentage
            - modelScoring: Model scoring percentage
            - modelCritiques: Model critiques percentage
        """
        model_voting = await self.model_voting_scorer.calculate_score(
            response, all_responses, judge_platform_id, use_llm=use_llm
        )
        model_scoring = await self.model_scoring_scorer.calculate_score(
            response, all_responses, judge_platform_id, use_llm=use_llm
        )
        model_critiques = await self.model_critiques_scorer.calculate_score(
            response, all_responses, judge_platform_id, use_llm=use_llm
        )
        
        return MultiJudgeAIReviewSubScore(
            modelVoting=model_voting,
            modelScoring=model_scoring,
            modelCritiques=model_critiques,
        )

    # Legacy method names for backward compatibility
    async def calculate_model_voting(
        self, response: str, all_responses: Dict[str, str], judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate model voting percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Model voting percentage (0-100)
        """
        return await self.model_voting_scorer.calculate_score(
            response, all_responses, judge_platform_id, use_llm=use_llm
        )

    async def calculate_model_scoring(
        self, response: str, all_responses: Dict[str, str], judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate model scoring percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Model scoring percentage (0-100)
        """
        return await self.model_scoring_scorer.calculate_score(
            response, all_responses, judge_platform_id, use_llm=use_llm
        )

    async def calculate_model_critiques(
        self, response: str, all_responses: Dict[str, str], judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate model critiques percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Model critiques percentage (0-100)
        """
        return await self.model_critiques_scorer.calculate_score(
            response, all_responses, judge_platform_id, use_llm=use_llm
        )

