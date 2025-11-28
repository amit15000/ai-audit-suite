"""Service for detecting outliers based on consensus scores."""
from __future__ import annotations

import structlog
from typing import Any, Dict, List, Tuple

logger = structlog.get_logger(__name__)


class OutlierDetector:
    """Service for detecting outliers with low consensus scores."""

    @staticmethod
    def detect_outliers(
        consensus_scores: Dict[str, float],
        threshold: float | None = None,
        method: str = "threshold",
    ) -> List[Tuple[str, float]]:
        """Detect outliers based on consensus scores.

        Args:
            consensus_scores: Dictionary mapping identifier to consensus score
            threshold: Optional threshold for outlier detection.
                       If None, uses statistical method (mean - 1.5 * std)
            method: Detection method - "threshold" or "statistical"

        Returns:
            List of tuples (identifier, consensus_score) for detected outliers,
            sorted by consensus score (lowest first)
        """
        if not consensus_scores:
            raise ValueError("Consensus scores cannot be empty")

        logger.debug(
            "outlier.detect_start",
            scores_count=len(consensus_scores),
            method=method,
        )

        if method == "statistical":
            threshold = OutlierDetector._calculate_statistical_threshold(
                consensus_scores
            )

        if threshold is None:
            raise ValueError("Threshold must be provided for threshold method")

        outliers: List[Tuple[str, float]] = []

        for response_id, score in consensus_scores.items():
            if score < threshold:
                outliers.append((response_id, score))

        # Sort by consensus score (lowest first - most outlier-like)
        outliers.sort(key=lambda x: x[1])

        logger.debug(
            "outlier.detect_complete",
            outliers_count=len(outliers),
            threshold=threshold,
        )

        return outliers

    @staticmethod
    def _calculate_statistical_threshold(
        consensus_scores: Dict[str, float],
    ) -> float:
        """Calculate statistical threshold using mean - 1.5 * standard deviation.

        Args:
            consensus_scores: Dictionary of consensus scores

        Returns:
            Threshold value below which responses are considered outliers
        """
        if len(consensus_scores) < 2:
            # Not enough data for statistical analysis
            return 0.0

        scores = list(consensus_scores.values())

        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / len(scores)
        std_dev = variance ** 0.5

        # Use 1.5 * std_dev below mean (similar to IQR method)
        threshold = mean - 1.5 * std_dev

        # Ensure threshold is not negative (similarity scores are typically 0-1)
        threshold = max(0.0, threshold)

        logger.debug(
            "outlier.statistical_threshold",
            mean=mean,
            std_dev=std_dev,
            threshold=threshold,
        )

        return threshold

    @staticmethod
    def get_outlier_analysis(
        consensus_scores: Dict[str, float],
        similarity_matrix: Dict[str, Dict[str, float]] | None = None,
    ) -> Dict[str, Any]:
        """Get comprehensive outlier analysis.

        Args:
            consensus_scores: Dictionary mapping identifier to consensus score
            similarity_matrix: Optional similarity matrix for detailed analysis

        Returns:
            Dictionary containing:
            - outliers: List of outlier identifiers
            - threshold: Detection threshold used
            - statistics: Mean, std_dev, min, max of consensus scores
            - outlier_details: Detailed information about each outlier
        """
        if not consensus_scores:
            raise ValueError("Consensus scores cannot be empty")

        threshold = OutlierDetector._calculate_statistical_threshold(
            consensus_scores
        )
        outliers = OutlierDetector.detect_outliers(
            consensus_scores, threshold=threshold, method="threshold"
        )

        scores = list(consensus_scores.values())
        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / len(scores)
        std_dev = variance ** 0.5

        outlier_details = []
        for outlier_id, score in outliers:
            detail = {
                "id": outlier_id,
                "consensus_score": score,
                "deviation_from_mean": score - mean,
                "deviation_in_std": (score - mean) / std_dev if std_dev > 0 else 0,
            }

            # Add similarity details if matrix provided
            if similarity_matrix and outlier_id in similarity_matrix:
                similarities = similarity_matrix[outlier_id]
                detail["avg_similarity_to_others"] = sum(
                    sim
                    for other_id, sim in similarities.items()
                    if other_id != outlier_id
                ) / max(1, len(similarities) - 1)

            outlier_details.append(detail)

        return {
            "outliers": [outlier_id for outlier_id, _ in outliers],
            "threshold": threshold,
            "statistics": {
                "mean": mean,
                "std_dev": std_dev,
                "min": min(scores),
                "max": max(scores),
                "count": len(scores),
            },
            "outlier_details": outlier_details,
        }

