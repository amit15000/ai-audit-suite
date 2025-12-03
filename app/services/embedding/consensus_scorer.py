"""Service for calculating consensus scores based on similarity metrics."""
from __future__ import annotations

import structlog
from typing import Dict, List

logger = structlog.get_logger(__name__)


class ConsensusScorer:
    """Service for calculating consensus scores based on similarity to other responses."""

    @staticmethod
    def calculate_consensus_scores(
        similarity_matrix: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        """Calculate consensus score for each response based on similarity to others.

        Consensus score is the average similarity of a response to all other responses.
        Higher scores indicate the response is more similar to the group (higher consensus).
        
        Enhanced to calculate agreement percentage across models.
        Example: 4 models agree → 90% consensus

        Args:
            similarity_matrix: Nested dictionary of pairwise similarities

        Returns:
            Dictionary mapping identifier to consensus score (0-1 range, typically)

        Example:
            {
                "openai": 0.85,
                "gemini": 0.82,
                "groq": 0.65,  # Lower consensus - potential outlier
            }
        """
        if not similarity_matrix:
            raise ValueError("Similarity matrix cannot be empty")

        logger.debug(
            "consensus.calculate_start",
            matrix_size=len(similarity_matrix),
        )

        consensus_scores: Dict[str, float] = {}

        for response_id, similarities in similarity_matrix.items():
            # Get all similarities to other responses (exclude self-similarity)
            other_similarities = [
                sim
                for other_id, sim in similarities.items()
                if other_id != response_id
            ]

            if not other_similarities:
                # Only one response, consensus is undefined
                consensus_scores[response_id] = 1.0
            else:
                # Average similarity to all other responses
                avg_similarity = sum(other_similarities) / len(other_similarities)
                consensus_scores[response_id] = avg_similarity

        logger.debug(
            "consensus.calculate_complete",
            scores_count=len(consensus_scores),
        )

        return consensus_scores

    @staticmethod
    def calculate_agreement_percentage(
        similarity_matrix: Dict[str, Dict[str, float]],
        threshold: float = 0.7,
    ) -> Dict[str, float]:
        """Calculate agreement percentage for each model.
        
        Agreement percentage shows how many models agree with this model.
        Example: 4 models agree → 90% consensus
        
        Args:
            similarity_matrix: Nested dictionary of pairwise similarities
            threshold: Similarity threshold to consider as "agreement" (default: 0.7)
            
        Returns:
            Dictionary mapping identifier to agreement percentage (0-100)
        """
        if not similarity_matrix:
            raise ValueError("Similarity matrix cannot be empty")
        
        total_models = len(similarity_matrix)
        agreement_percentages: Dict[str, float] = {}
        
        for response_id, similarities in similarity_matrix.items():
            # Count how many models agree (similarity >= threshold)
            agreeing_models = sum(
                1 for other_id, sim in similarities.items()
                if other_id != response_id and sim >= threshold
            )
            
            # Calculate percentage (include self, so total is total_models)
            # Agreement percentage = (agreeing_models + 1) / total_models * 100
            agreement_pct = ((agreeing_models + 1) / total_models) * 100
            agreement_percentages[response_id] = agreement_pct
        
        return agreement_percentages

    @staticmethod
    def calculate_weighted_consensus_scores(
        similarity_matrix: Dict[str, Dict[str, float]],
        weights: Dict[str, float] | None = None,
    ) -> Dict[str, float]:
        """Calculate weighted consensus scores.

        Args:
            similarity_matrix: Nested dictionary of pairwise similarities
            weights: Optional weights for each response (defaults to equal weights)

        Returns:
            Dictionary mapping identifier to weighted consensus score
        """
        if not similarity_matrix:
            raise ValueError("Similarity matrix cannot be empty")

        consensus_scores: Dict[str, float] = {}

        # Default to equal weights if not provided
        if weights is None:
            weights = {id: 1.0 for id in similarity_matrix.keys()}

        for response_id, similarities in similarity_matrix.items():
            weighted_sum = 0.0
            total_weight = 0.0

            for other_id, similarity in similarities.items():
                if other_id != response_id:
                    weight = weights.get(other_id, 1.0)
                    weighted_sum += similarity * weight
                    total_weight += weight

            if total_weight == 0:
                consensus_scores[response_id] = 1.0
            else:
                consensus_scores[response_id] = weighted_sum / total_weight

        return consensus_scores

