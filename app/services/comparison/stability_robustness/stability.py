"""Stability score calculation for stability & robustness detection."""
from __future__ import annotations

from typing import Dict

from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService
from app.services.comparison.stability_robustness.utils import clamp_percentage


class StabilityScorer:
    """Calculates stability percentage."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        similarity_service: SimilarityService,
    ):
        """Initialize stability scorer.
        
        Args:
            embedding_service: Service for generating embeddings
            similarity_service: Service for calculating similarity
        """
        self.embedding_service = embedding_service
        self.similarity_service = similarity_service

    async def calculate_score(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate stability percentage (0-100).
        
        Measures how consistent the response is across multiple runs.
        Higher percentage = more stable/consistent.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
            
        Returns:
            Stability percentage (0-100)
        """
        if len(all_responses) <= 1:
            # Only one response, assume high stability
            return 98.0
        
        similarities = []
        
        if use_embeddings:
            try:
                response_embedding = await self.embedding_service.generate_embedding(response)
                
                for other_response in all_responses.values():
                    if other_response == response:
                        continue
                    
                    try:
                        other_embedding = await self.embedding_service.generate_embedding(other_response)
                        similarity = self.similarity_service.cosine_similarity(
                            response_embedding, other_embedding
                        )
                        similarities.append(max(0, similarity))
                    except Exception:
                        continue
            except Exception:
                # Fall back to word-based similarity
                similarities = self._calculate_word_based_similarities(response, all_responses)
        else:
            similarities = self._calculate_word_based_similarities(response, all_responses)
        
        if len(similarities) == 0:
            return 98.0
        
        # Calculate average similarity (stability)
        avg_similarity = sum(similarities) / len(similarities)
        
        # Convert to percentage (0-100)
        stability_percentage = avg_similarity * 100
        
        return clamp_percentage(stability_percentage)

    def _calculate_word_based_similarities(
        self, response: str, all_responses: Dict[str, str]
    ) -> list[float]:
        """Calculate word-based similarities."""
        response_words = set(response.lower().split())
        response_words = {w for w in response_words if len(w) > 2}
        
        similarities = []
        for other_response in all_responses.values():
            if other_response == response:
                continue
            
            other_words = set(other_response.lower().split())
            other_words = {w for w in other_words if len(w) > 2}
            
            if response_words and other_words:
                intersection = len(response_words & other_words)
                union = len(response_words | other_words)
                similarity = intersection / union if union > 0 else 0
                similarities.append(similarity)
        
        return similarities

