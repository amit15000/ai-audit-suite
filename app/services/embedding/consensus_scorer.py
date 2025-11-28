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

