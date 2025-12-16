"""Service for calculating prompt sensitivity test scores and sub-scores."""
from __future__ import annotations

from typing import Dict

from app.domain.schemas import PromptSensitivitySubScore
from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService
from app.services.comparison.prompt_sensitivity import SensitivityScorer


class PromptSensitivityScorer:
    """Service for calculating prompt sensitivity test scores and sub-scores."""

    def __init__(self):
        """Initialize prompt sensitivity scorer with sub-score calculators."""
        self.embedding_service = EmbeddingService()
        self.similarity_service = SimilarityService()
        
        # Initialize sub-score calculators
        self.sensitivity_scorer = SensitivityScorer(
            self.embedding_service, self.similarity_service
        )

    async def calculate_sub_scores(
        self,
        response: str,
        all_responses: Dict[str, str],
        use_embeddings: bool = True,
    ) -> PromptSensitivitySubScore:
        """Calculate the prompt sensitivity sub-score.
        
        Measures how sensitive the response is to prompt variations.
        Higher percentage = more sensitive (less robust).
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings (default: True)
        
        Returns:
            PromptSensitivitySubScore with:
            - sensitivity: Sensitivity percentage (0-100)
        """
        sensitivity = await self.sensitivity_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )
        
        return PromptSensitivitySubScore(
            sensitivity=sensitivity,
        )

    # Legacy method name for backward compatibility
    async def calculate_sensitivity(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate sensitivity percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
            
        Returns:
            Sensitivity percentage (0-100)
        """
        return await self.sensitivity_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )

