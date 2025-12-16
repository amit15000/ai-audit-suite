"""Four model agree score calculation for multi-LLM consensus detection."""
from __future__ import annotations

from typing import Dict

from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService


class FourModelAgreeScorer:
    """Calculates percentage of 4 model agreement."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        similarity_service: SimilarityService,
    ):
        """Initialize four model agree scorer.
        
        Args:
            embedding_service: Service for generating embeddings
            similarity_service: Service for calculating similarity
        """
        self.embedding_service = embedding_service
        self.similarity_service = similarity_service

    async def calculate_score(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of 4 model agreement (0-100).
        
        Measures how many groups of 4 models agree with each other.
        Higher percentage = more consensus among models.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
        """
        if len(all_responses) < 4:
            # Need at least 4 responses for 4-model agreement
            return 0.0
        
        # Generate embeddings if needed
        if use_embeddings:
            try:
                response_embedding = await self.embedding_service.generate_embedding(response)
                other_embeddings = {}
                for key, other_response in all_responses.items():
                    if other_response != response:
                        try:
                            other_embeddings[key] = await self.embedding_service.generate_embedding(other_response)
                        except Exception:
                            continue
                
                if len(other_embeddings) < 3:
                    # Fall back to word-based similarity
                    return self._calculate_four_model_agree_word_based(response, all_responses)
                
                # Calculate similarities
                similarities = []
                for other_embedding in other_embeddings.values():
                    similarity = self.similarity_service.cosine_similarity(
                        response_embedding, other_embedding
                    )
                    similarities.append(max(0, similarity))  # Ensure non-negative
                
                # Count how many models have high agreement (similarity > 0.8)
                high_agreement_count = sum(1 for sim in similarities if sim >= 0.8)
                
                # Calculate percentage: if 3+ models agree (out of 4+), that's high agreement
                if len(similarities) >= 3:
                    # Percentage of models that agree strongly
                    agreement_rate = high_agreement_count / len(similarities)
                    return min(100.0, agreement_rate * 100)
                else:
                    return 0.0
            except Exception:
                # Fall back to word-based similarity
                return self._calculate_four_model_agree_word_based(response, all_responses)
        else:
            return self._calculate_four_model_agree_word_based(response, all_responses)

    def _calculate_four_model_agree_word_based(
        self, response: str, all_responses: Dict[str, str]
    ) -> float:
        """Calculate 4-model agreement using word-based similarity."""
        response_words = set(response.lower().split())
        response_words = {w for w in response_words if len(w) > 2}
        
        if not response_words:
            return 0.0
        
        similarities = []
        for other_response in all_responses.values():
            if other_response == response:
                continue
            
            other_words = set(other_response.lower().split())
            other_words = {w for w in other_words if len(w) > 2}
            
            if other_words:
                intersection = len(response_words & other_words)
                union = len(response_words | other_words)
                similarity = intersection / union if union > 0 else 0
                similarities.append(similarity)
        
        if len(similarities) < 3:
            return 0.0
        
        # Count high agreement (similarity > 0.7 for word-based)
        high_agreement_count = sum(1 for sim in similarities if sim >= 0.7)
        agreement_rate = high_agreement_count / len(similarities)
        return min(100.0, agreement_rate * 100)

