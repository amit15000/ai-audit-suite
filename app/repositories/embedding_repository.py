"""Repository for embedding and similarity data access."""
from __future__ import annotations

from typing import Any

from app.domain.models import Embedding, SimilarityAnalysis
from app.repositories.base import BaseRepository


class EmbeddingRepository(BaseRepository[Embedding]):
    """Repository for embedding data access."""

    def create(
        self,
        request_id: str,
        provider: str,
        text: str,
        embedding_vector: list[float],
        model_name: str,
    ) -> Embedding:
        """Create a new embedding record.

        Args:
            request_id: Request ID to group embeddings
            provider: LLM provider/adapter ID
            text: The text that was embedded
            embedding_vector: Embedding vector as list of floats
            model_name: Name of the embedding model used

        Returns:
            Created Embedding instance
        """
        session = self._get_session()
        try:
            embedding = Embedding(
                request_id=request_id,
                provider=provider,
                text=text,
                embedding_vector=embedding_vector,
                model_name=model_name,
                embedding_dimension=len(embedding_vector),
            )
            session.add(embedding)
            session.commit()
            session.refresh(embedding)
            return embedding
        except Exception:
            session.rollback()
            raise

    def get_by_request_id(self, request_id: str) -> list[Embedding]:
        """Get all embeddings for a request ID.

        Args:
            request_id: Request ID to filter by

        Returns:
            List of Embedding instances
        """
        session = self._get_session()
        return (
            session.query(Embedding)
            .filter(Embedding.request_id == request_id)
            .order_by(Embedding.created_at.desc())
            .all()
        )

    def get_by_provider(self, provider: str, request_id: str | None = None) -> list[Embedding]:
        """Get embeddings for a provider, optionally filtered by request_id.

        Args:
            provider: Provider ID to filter by
            request_id: Optional request ID to filter by

        Returns:
            List of Embedding instances
        """
        session = self._get_session()
        query = session.query(Embedding).filter(Embedding.provider == provider)
        if request_id:
            query = query.filter(Embedding.request_id == request_id)
        return query.order_by(Embedding.created_at.desc()).all()


class SimilarityAnalysisRepository(BaseRepository[SimilarityAnalysis]):
    """Repository for similarity analysis data access."""

    def create(
        self,
        request_id: str,
        similarity_matrix: dict[str, dict[str, float]],
        consensus_scores: dict[str, float],
        outliers: list[str] | None = None,
        outlier_threshold: str | None = None,
        statistics: dict[str, Any] | None = None,
    ) -> SimilarityAnalysis:
        """Create a new similarity analysis record.

        Args:
            request_id: Request ID to group analyses
            similarity_matrix: Full similarity matrix
            consensus_scores: Consensus scores for each provider
            outliers: Optional list of outlier provider IDs
            outlier_threshold: Optional threshold used for outlier detection
            statistics: Optional statistical summary

        Returns:
            Created SimilarityAnalysis instance
        """
        session = self._get_session()
        try:
            analysis = SimilarityAnalysis(
                request_id=request_id,
                similarity_matrix=similarity_matrix,
                consensus_scores=consensus_scores,
                outliers=outliers,
                outlier_threshold=outlier_threshold,
                statistics=statistics,
            )
            session.add(analysis)
            session.commit()
            session.refresh(analysis)
            return analysis
        except Exception:
            session.rollback()
            raise

    def get_by_request_id(self, request_id: str) -> SimilarityAnalysis | None:
        """Get similarity analysis for a request ID.

        Args:
            request_id: Request ID to filter by

        Returns:
            SimilarityAnalysis instance or None if not found
        """
        session = self._get_session()
        return (
            session.query(SimilarityAnalysis)
            .filter(SimilarityAnalysis.request_id == request_id)
            .order_by(SimilarityAnalysis.created_at.desc())
            .first()
        )

