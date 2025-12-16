"""Deviation map scoring modules."""
from __future__ import annotations

from app.services.comparison.deviation_map.sentence_level_comparison import SentenceLevelComparisonScorer
from app.services.comparison.deviation_map.highlighted_differences import HighlightedDifferencesScorer
from app.services.comparison.deviation_map.color_coded_conflict_areas import ColorCodedConflictAreasScorer

__all__ = [
    "SentenceLevelComparisonScorer",
    "HighlightedDifferencesScorer",
    "ColorCodedConflictAreasScorer",
]

