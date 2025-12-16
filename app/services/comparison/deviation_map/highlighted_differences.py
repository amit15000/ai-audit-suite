"""Highlighted differences score calculation for deviation map detection."""
from __future__ import annotations

from typing import Dict

from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService
from app.services.comparison.deviation_map.base import DeviationMapBase


class HighlightedDifferencesScorer(DeviationMapBase):
    """Calculates percentage of highlighted differences."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        similarity_service: SimilarityService,
    ):
        """Initialize highlighted differences scorer.
        
        Args:
            embedding_service: Service for generating embeddings
            similarity_service: Service for calculating similarity
        """
        self.embedding_service = embedding_service
        self.similarity_service = similarity_service

    async def calculate_score(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of highlighted differences (0-100).
        
        Measures how many differences are identified and highlighted.
        Higher percentage = more differences detected.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
        """
        # Split into sentences
        response_sentences = self._split_into_sentences(response)
        
        if len(response_sentences) == 0:
            return 0.0
        
        differences_count = 0
        total_comparisons = 0
        
        for sentence in response_sentences:
            if len(sentence.strip()) < 10:
                continue
            
            for other_response in all_responses.values():
                if other_response == response:
                    continue
                
                total_comparisons += 1
                other_sentences = self._split_into_sentences(other_response)
                
                # Find most similar sentence
                max_similarity = 0.0
                for other_sentence in other_sentences:
                    if use_embeddings:
                        try:
                            sent_emb = await self.embedding_service.generate_embedding(sentence)
                            other_emb = await self.embedding_service.generate_embedding(other_sentence)
                            similarity = self.similarity_service.cosine_similarity(sent_emb, other_emb)
                            max_similarity = max(max_similarity, similarity)
                        except Exception:
                            similarity = self._sentence_similarity_word_based(sentence, other_sentence)
                            max_similarity = max(max_similarity, similarity)
                    else:
                        similarity = self._sentence_similarity_word_based(sentence, other_sentence)
                        max_similarity = max(max_similarity, similarity)
                
                # If similarity is low, it's a difference
                if max_similarity < 0.6:  # Threshold for difference
                    differences_count += 1
        
        # Calculate percentage
        if total_comparisons > 0:
            percentage = (differences_count / total_comparisons) * 100
            return min(100.0, percentage)
        return 0.0

