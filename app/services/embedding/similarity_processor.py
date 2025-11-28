"""Orchestrator service for embedding and similarity processing pipeline."""
from __future__ import annotations

import structlog
from typing import Any, Dict, List

from app.repositories.embedding_repository import (
    EmbeddingRepository,
    SimilarityAnalysisRepository,
)
from app.services.embedding.consensus_scorer import ConsensusScorer
from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.outlier_detector import OutlierDetector
from app.services.embedding.similarity_service import SimilarityService

logger = structlog.get_logger(__name__)


class SimilarityProcessor:
    """Orchestrator for the complete embedding and similarity processing pipeline."""

    def __init__(
        self,
        embedding_repo: EmbeddingRepository | None = None,
        similarity_repo: SimilarityAnalysisRepository | None = None,
    ) -> None:
        """Initialize the similarity processor with services and repositories.

        Args:
            embedding_repo: Optional embedding repository (creates new if not provided)
            similarity_repo: Optional similarity analysis repository (creates new if not provided)
        """
        self.embedding_service = EmbeddingService()
        self.similarity_service = SimilarityService()
        self.consensus_scorer = ConsensusScorer()
        self.outlier_detector = OutlierDetector()
        self.embedding_repo = embedding_repo or EmbeddingRepository()
        self.similarity_repo = similarity_repo or SimilarityAnalysisRepository()

    async def process_responses(
        self,
        request_id: str,
        responses: Dict[str, str],
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Process responses through the complete embedding and similarity pipeline.

        Args:
            request_id: Request ID to group the analysis
            responses: Dictionary mapping provider_id to response text
            persist: Whether to persist results to database (default: True)

        Returns:
            Dictionary containing:
            - embeddings: Dict mapping provider_id to embedding vector
            - similarity_matrix: Nested dict of pairwise similarities
            - consensus_scores: Dict mapping provider_id to consensus score
            - outliers: List of outlier provider IDs
            - outlier_analysis: Detailed outlier analysis
        """
        if not responses:
            raise ValueError("Responses dictionary cannot be empty")

        logger.info(
            "similarity.process_start",
            request_id=request_id,
            responses_count=len(responses),
        )

        # Step 1: Generate embeddings for all responses
        logger.debug("similarity.step_embeddings", request_id=request_id)
        embeddings_dict: Dict[str, List[float]] = {}
        texts = list(responses.values())
        providers = list(responses.keys())

        # Generate embeddings in batch for efficiency
        embedding_vectors = await self.embedding_service.generate_embeddings_batch(
            texts
        )

        # Map embeddings back to providers
        for provider, embedding in zip(providers, embedding_vectors):
            embeddings_dict[provider] = embedding

            # Persist embedding if requested
            if persist:
                try:
                    self.embedding_repo.create(
                        request_id=request_id,
                        provider=provider,
                        text=responses[provider],
                        embedding_vector=embedding,
                        model_name=self.embedding_service.model_name,
                    )
                except Exception as e:
                    logger.warning(
                        "similarity.embedding_persist_failed",
                        request_id=request_id,
                        provider=provider,
                        error=str(e),
                    )

        # Step 2: Compute similarity matrix
        logger.debug("similarity.step_matrix", request_id=request_id)
        similarity_matrix = self.similarity_service.compute_similarity_matrix(
            embeddings_dict
        )

        # Step 3: Calculate consensus scores
        logger.debug("similarity.step_consensus", request_id=request_id)
        consensus_scores = self.consensus_scorer.calculate_consensus_scores(
            similarity_matrix
        )

        # Step 4: Detect outliers
        logger.debug("similarity.step_outliers", request_id=request_id)
        outlier_analysis = self.outlier_detector.get_outlier_analysis(
            consensus_scores, similarity_matrix
        )

        outliers = outlier_analysis["outliers"]

        # Step 5: Persist similarity analysis if requested
        if persist:
            try:
                self.similarity_repo.create(
                    request_id=request_id,
                    similarity_matrix=similarity_matrix,
                    consensus_scores=consensus_scores,
                    outliers=outliers,
                    outlier_threshold=str(outlier_analysis["threshold"]),
                    statistics=outlier_analysis["statistics"],
                )
            except Exception as e:
                logger.warning(
                    "similarity.analysis_persist_failed",
                    request_id=request_id,
                    error=str(e),
                )

        logger.info(
            "similarity.process_complete",
            request_id=request_id,
            outliers_count=len(outliers),
        )

        return {
            "embeddings": embeddings_dict,
            "similarity_matrix": similarity_matrix,
            "consensus_scores": consensus_scores,
            "outliers": outliers,
            "outlier_analysis": outlier_analysis,
        }

    async def get_analysis(self, request_id: str) -> Dict[str, Any] | None:
        """Retrieve stored similarity analysis for a request ID.

        Args:
            request_id: Request ID to retrieve analysis for

        Returns:
            Dictionary containing analysis data or None if not found
        """
        analysis = self.similarity_repo.get_by_request_id(request_id)
        if not analysis:
            return None

        embeddings = self.embedding_repo.get_by_request_id(request_id)
        embeddings_dict = {
            emb.provider: emb.embedding_vector for emb in embeddings
        }

        return {
            "embeddings": embeddings_dict,
            "similarity_matrix": analysis.similarity_matrix,
            "consensus_scores": analysis.consensus_scores,
            "outliers": analysis.outliers or [],
            "outlier_analysis": {
                "outliers": analysis.outliers or [],
                "threshold": float(analysis.outlier_threshold)
                if analysis.outlier_threshold
                else None,
                "statistics": analysis.statistics or {},
            },
        }

