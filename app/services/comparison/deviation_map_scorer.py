"""Service for calculating deviation map scores and sub-scores."""
from __future__ import annotations

from typing import Dict

from app.domain.schemas import DeviationMapSubScore
from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService
from app.services.comparison.deviation_map import (
    SentenceLevelComparisonScorer,
    HighlightedDifferencesScorer,
    ColorCodedConflictAreasScorer,
)


class DeviationMapScorer:
    """Service for calculating deviation map scores and sub-scores."""

    def __init__(self):
        """Initialize deviation map scorer with sub-score calculators."""
        self.embedding_service = EmbeddingService()
        self.similarity_service = SimilarityService()
        
        # Initialize sub-score calculators
        self.sentence_level_comparison_scorer = SentenceLevelComparisonScorer(
            self.embedding_service, self.similarity_service
        )
        self.highlighted_differences_scorer = HighlightedDifferencesScorer(
            self.embedding_service, self.similarity_service
        )
        self.color_coded_conflict_areas_scorer = ColorCodedConflictAreasScorer(
            self.embedding_service, self.similarity_service
        )

    async def calculate_sub_scores(
        self,
        response: str,
        all_responses: Dict[str, str],
        use_embeddings: bool = True,
    ) -> DeviationMapSubScore:
        """Calculate the 3 deviation map sub-scores.
        
        Uses sentence-level comparison to identify deviations and conflicts.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings (default: True)
        
        Returns:
            DeviationMapSubScore with:
            - sentenceLevelComparison: Percentage of sentence-level comparison (0-100)
            - highlightedDifferences: Percentage of highlighted differences (0-100)
            - colorCodedConflictAreas: Percentage of color-coded conflict areas (0-100)
        """
        if len(all_responses) < 2:
            return DeviationMapSubScore(
                sentenceLevelComparison=0.0,
                highlightedDifferences=0.0,
                colorCodedConflictAreas=0.0
            )
        
        # Calculate deviation metrics
        sentence_level = await self.sentence_level_comparison_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )
        highlighted_differences = await self.highlighted_differences_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )
        color_coded_conflicts = await self.color_coded_conflict_areas_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )
        
        return DeviationMapSubScore(
            sentenceLevelComparison=sentence_level,
            highlightedDifferences=highlighted_differences,
            colorCodedConflictAreas=color_coded_conflicts,
        )

    # Legacy method names for backward compatibility
    async def calculate_sentence_level_comparison(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of sentence-level comparison (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
            
        Returns:
            Percentage of sentence-level comparison (0-100)
        """
        return await self.sentence_level_comparison_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )

    async def calculate_highlighted_differences(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of highlighted differences (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
            
        Returns:
            Percentage of highlighted differences (0-100)
        """
        return await self.highlighted_differences_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )

    async def calculate_color_coded_conflict_areas(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of color-coded conflict areas (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
            
        Returns:
            Percentage of color-coded conflict areas (0-100)
        """
        return await self.color_coded_conflict_areas_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )

