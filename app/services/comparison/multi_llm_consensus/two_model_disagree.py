"""Two model disagree score calculation for multi-LLM consensus detection."""
from __future__ import annotations

from typing import Dict

from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService


class TwoModelDisagreeScorer:
    """Calculates percentage of 2 model disagreement."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        similarity_service: SimilarityService,
    ):
        """Initialize two model disagree scorer.
        
        Args:
            embedding_service: Service for generating embeddings
            similarity_service: Service for calculating similarity
        """
        self.embedding_service = embedding_service
        self.similarity_service = similarity_service

    async def calculate_score(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of 2 model disagreement (0-100).
        
        Measures how many pairs of 2 models disagree with each other.
        Higher percentage = more disagreement among models.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
        """
        if len(all_responses) < 2:
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
                
                if len(other_embeddings) < 1:
                    return self._calculate_two_model_disagree_word_based(response, all_responses)
                
                # Calculate similarities
                similarities = []
                for other_embedding in other_embeddings.values():
                    similarity = self.similarity_service.cosine_similarity(
                        response_embedding, other_embedding
                    )
                    similarities.append(max(0, similarity))
                
                # Count low agreement (similarity < 0.5 indicates disagreement)
                low_agreement_count = sum(1 for sim in similarities if sim < 0.5)
                
                if len(similarities) > 0:
                    disagreement_rate = low_agreement_count / len(similarities)
                    return min(100.0, disagreement_rate * 100)
                else:
                    return 0.0
            except Exception:
                return self._calculate_two_model_disagree_word_based(response, all_responses)
        else:
            return self._calculate_two_model_disagree_word_based(response, all_responses)

    def _calculate_two_model_disagree_word_based(
        self, response: str, all_responses: Dict[str, str]
    ) -> float:
        """Calculate 2-model disagreement using word-based similarity."""
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
        
        if len(similarities) == 0:
            return 0.0
        
        # Count low agreement (similarity < 0.4 for word-based indicates disagreement)
        low_agreement_count = sum(1 for sim in similarities if sim < 0.4)
        disagreement_rate = low_agreement_count / len(similarities)
        return min(100.0, disagreement_rate * 100)

