"""Sentence level comparison score calculation for deviation map detection."""
from __future__ import annotations

from typing import Dict

from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService
from app.services.comparison.deviation_map.base import DeviationMapBase


class SentenceLevelComparisonScorer(DeviationMapBase):
    """Calculates percentage of sentence-level comparison."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        similarity_service: SimilarityService,
    ):
        """Initialize sentence level comparison scorer.
        
        Args:
            embedding_service: Service for generating embeddings
            similarity_service: Service for calculating similarity
        """
        self.embedding_service = embedding_service
        self.similarity_service = similarity_service

    async def calculate_score(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of sentence-level comparison (0-100).
        
        Measures how many sentences are compared across responses.
        Higher percentage = more comprehensive sentence-level analysis.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
        """
        # Split response into sentences
        response_sentences = self._split_into_sentences(response)
        
        if len(response_sentences) == 0:
            return 0.0
        
        # Compare each sentence with other responses
        compared_count = 0
        
        for sentence in response_sentences:
            if len(sentence.strip()) < 10:  # Skip very short sentences
                continue
            
            # Check if this sentence has matches in other responses
            has_match = False
            for other_response in all_responses.values():
                if other_response == response:
                    continue
                
                other_sentences = self._split_into_sentences(other_response)
                for other_sentence in other_sentences:
                    if use_embeddings:
                        try:
                            # Use semantic similarity
                            sent_emb = await self.embedding_service.generate_embedding(sentence)
                            other_emb = await self.embedding_service.generate_embedding(other_sentence)
                            similarity = self.similarity_service.cosine_similarity(sent_emb, other_emb)
                            if similarity > 0.5:  # Similar enough to be compared
                                has_match = True
                                break
                        except Exception:
                            # Fall back to word-based
                            if self._sentences_similar_word_based(sentence, other_sentence):
                                has_match = True
                                break
                    else:
                        if self._sentences_similar_word_based(sentence, other_sentence):
                            has_match = True
                            break
                
                if has_match:
                    break
            
            if has_match:
                compared_count += 1
        
        # Calculate percentage
        if len(response_sentences) > 0:
            percentage = (compared_count / len(response_sentences)) * 100
            return min(100.0, percentage)
        return 0.0

