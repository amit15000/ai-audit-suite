"""Color-coded conflict areas score calculation for deviation map detection."""
from __future__ import annotations

from typing import Dict

from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService
from app.services.comparison.deviation_map.base import DeviationMapBase


class ColorCodedConflictAreasScorer(DeviationMapBase):
    """Calculates percentage of color-coded conflict areas."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        similarity_service: SimilarityService,
    ):
        """Initialize color-coded conflict areas scorer.
        
        Args:
            embedding_service: Service for generating embeddings
            similarity_service: Service for calculating similarity
        """
        self.embedding_service = embedding_service
        self.similarity_service = similarity_service

    async def calculate_score(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of color-coded conflict areas (0-100).
        
        Measures how many areas have conflicts that need color-coding.
        Higher percentage = more conflict areas detected.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
        """
        # Split into sentences
        response_sentences = self._split_into_sentences(response)
        
        if len(response_sentences) == 0:
            return 0.0
        
        conflict_areas = 0
        
        # Check for contradictory information
        for i, sentence in enumerate(response_sentences):
            if len(sentence.strip()) < 10:
                continue
            
            # Check against other responses for contradictions
            for other_response in all_responses.values():
                if other_response == response:
                    continue
                
                other_sentences = self._split_into_sentences(other_response)
                
                # Look for contradictory sentences
                for other_sentence in other_sentences:
                    # Note: _are_contradictory is synchronous, no await needed
                    if self._are_contradictory(sentence, other_sentence, use_embeddings):
                        conflict_areas += 1
                        break
        
        # Calculate percentage based on number of sentences
        if len(response_sentences) > 0:
            percentage = (conflict_areas / len(response_sentences)) * 100
            return min(100.0, percentage)
        return 0.0

