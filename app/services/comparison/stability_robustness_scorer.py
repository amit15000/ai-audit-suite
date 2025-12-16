"""Service for calculating stability & robustness test scores and sub-scores."""
from __future__ import annotations

from typing import Dict

from app.domain.schemas import StabilityRobustnessSubScore
from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService
from app.services.comparison.stability_robustness import StabilityScorer


class StabilityRobustnessScorer:
    """Service for calculating stability & robustness test scores and sub-scores."""

    def __init__(self):
        """Initialize stability & robustness scorer with sub-score calculators."""
        self.embedding_service = EmbeddingService()
        self.similarity_service = SimilarityService()
        
        # Initialize sub-score calculators
        self.stability_scorer = StabilityScorer(
            self.embedding_service, self.similarity_service
        )

    async def calculate_sub_scores(
        self,
        response: str,
        all_responses: Dict[str, str],
        use_embeddings: bool = True,
    ) -> StabilityRobustnessSubScore:
        """Calculate the stability & robustness sub-score.
        
        Measures consistency across multiple responses to assess stability.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings (default: True)
        
        Returns:
            StabilityRobustnessSubScore with:
            - stability: Stability percentage (0-100)
        """
        stability = await self.stability_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )
        
        return StabilityRobustnessSubScore(
            stability=stability,
        )

    # Legacy method name for backward compatibility
    async def calculate_stability(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate stability percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
            
        Returns:
            Stability percentage (0-100)
        """
        return await self.stability_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )

