"""Service for computing similarity metrics between embeddings."""
from __future__ import annotations

import structlog
from typing import Dict, List, Tuple

import numpy as np

logger = structlog.get_logger(__name__)


class SimilarityService:
    """Service for computing similarity metrics between embeddings."""

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Cosine similarity score between -1 and 1 (typically 0-1 for normalized embeddings)

        Raises:
            ValueError: If vectors have different dimensions or are empty
        """
        if not vec1 or not vec2:
            raise ValueError("Vectors cannot be empty")

        if len(vec1) != len(vec2):
            raise ValueError(
                f"Vectors must have same dimension: {len(vec1)} != {len(vec2)}"
            )

        try:
            v1 = np.array(vec1, dtype=np.float32)
            v2 = np.array(vec2, dtype=np.float32)

            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return float(similarity)

        except Exception as e:
            logger.error(
                "similarity.compute_error",
                error=str(e),
                vec1_dim=len(vec1),
                vec2_dim=len(vec2),
            )
            raise

    def compute_similarity_matrix(
        self, embeddings: Dict[str, List[float]]
    ) -> Dict[str, Dict[str, float]]:
        """Compute pairwise cosine similarity matrix for all embeddings.

        Args:
            embeddings: Dictionary mapping identifier (e.g., provider_id) to embedding vector

        Returns:
            Nested dictionary where similarity_matrix[id1][id2] = similarity score

        Example:
            {
                "openai": {"openai": 1.0, "gemini": 0.85, "groq": 0.78},
                "gemini": {"openai": 0.85, "gemini": 1.0, "groq": 0.82},
                ...
            }
        """
        if not embeddings:
            raise ValueError("Embeddings dictionary cannot be empty")

        logger.debug(
            "similarity.matrix_compute_start",
            embeddings_count=len(embeddings),
        )

        ids = list(embeddings.keys())
        similarity_matrix: Dict[str, Dict[str, float]] = {}

        for i, id1 in enumerate(ids):
            similarity_matrix[id1] = {}
            for j, id2 in enumerate(ids):
                if i == j:
                    # Self-similarity is always 1.0
                    similarity_matrix[id1][id2] = 1.0
                else:
                    similarity = self.cosine_similarity(
                        embeddings[id1], embeddings[id2]
                    )
                    similarity_matrix[id1][id2] = similarity

        logger.debug(
            "similarity.matrix_compute_complete",
            matrix_size=len(similarity_matrix),
        )

        return similarity_matrix

    def compute_pairwise_similarities(
        self, embeddings: Dict[str, List[float]]
    ) -> List[Tuple[str, str, float]]:
        """Compute all pairwise similarities (excluding self-similarities).

        Args:
            embeddings: Dictionary mapping identifier to embedding vector

        Returns:
            List of tuples (id1, id2, similarity_score) for all unique pairs
        """
        if not embeddings:
            raise ValueError("Embeddings dictionary cannot be empty")

        ids = list(embeddings.keys())
        similarities: List[Tuple[str, str, float]] = []

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                id1, id2 = ids[i], ids[j]
                similarity = self.cosine_similarity(
                    embeddings[id1], embeddings[id2]
                )
                similarities.append((id1, id2, similarity))

        return similarities

