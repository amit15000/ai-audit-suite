"""Service for calculating multi-LLM consensus scores and sub-scores."""
from __future__ import annotations

from typing import Dict

from app.domain.schemas import MultiLLMConsensusSubScore
from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService
from app.services.comparison.multi_llm_consensus import (
    FourModelAgreeScorer,
    TwoModelDisagreeScorer,
)


class MultiLLMConsensusScorer:
    """Service for calculating multi-LLM consensus scores and sub-scores."""

    def __init__(self):
        """Initialize multi-LLM consensus scorer with sub-score calculators."""
        self.embedding_service = EmbeddingService()
        self.similarity_service = SimilarityService()
        
        # Initialize sub-score calculators
        self.four_model_agree_scorer = FourModelAgreeScorer(
            self.embedding_service, self.similarity_service
        )
        self.two_model_disagree_scorer = TwoModelDisagreeScorer(
            self.embedding_service, self.similarity_service
        )

    async def calculate_sub_scores(
        self,
        response: str,
        all_responses: Dict[str, str],
        use_embeddings: bool = True,
    ) -> MultiLLMConsensusSubScore:
        """Calculate the 2 multi-LLM consensus sub-scores.
        
        Uses similarity comparison to determine agreement/disagreement percentages.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings (default: True)
        
        Returns:
            MultiLLMConsensusSubScore with:
            - fourModelAgree: Percentage of 4 model agreement (0-100)
            - twoModelDisagree: Percentage of 2 model disagreement (0-100)
        """
        if len(all_responses) < 2:
            # Need at least 2 responses for comparison
            return MultiLLMConsensusSubScore(
                fourModelAgree=0.0,
                twoModelDisagree=0.0
            )
        
        # Calculate consensus metrics
        four_model_agree = await self.four_model_agree_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )
        two_model_disagree = await self.two_model_disagree_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )
        
        return MultiLLMConsensusSubScore(
            fourModelAgree=four_model_agree,
            twoModelDisagree=two_model_disagree,
        )

    # Legacy method names for backward compatibility
    async def calculate_four_model_agree(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of 4 model agreement (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
            
        Returns:
            Percentage of 4 model agreement (0-100)
        """
        return await self.four_model_agree_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )

    async def calculate_two_model_disagree(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of 2 model disagreement (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
            
        Returns:
            Percentage of 2 model disagreement (0-100)
        """
        return await self.two_model_disagree_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )

