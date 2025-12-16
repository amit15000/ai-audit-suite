"""Service for calculating data extraction accuracy audit scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import DataExtractionAccuracySubScore
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.data_extraction_accuracy import (
    CompareExtractedTextWithGroundTruthScorer,
    DetectExtractionErrorsScorer,
    FlagMismatchedValuesScorer,
)


class DataExtractionAccuracyScorer:
    """Service for calculating data extraction accuracy audit scores and sub-scores."""

    def __init__(self):
        """Initialize data extraction accuracy scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.compare_extracted_text_with_ground_truth_scorer = CompareExtractedTextWithGroundTruthScorer(
            self.ai_service
        )
        self.detect_extraction_errors_scorer = DetectExtractionErrorsScorer(self.ai_service)
        self.flag_mismatched_values_scorer = FlagMismatchedValuesScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        ground_truth: str = "",
        judge_platform_id: str = "",
        use_llm: bool = False,
    ) -> DataExtractionAccuracySubScore:
        """Calculate the 3 data extraction accuracy sub-scores.
        
        Args:
            response: The response text to evaluate
            ground_truth: Ground truth text for comparison (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            DataExtractionAccuracySubScore with percentages (0-100) for:
            - compareExtractedTextWithGroundTruth: Compare extracted text with ground truth percentage
            - detectExtractionErrors: Detect extraction errors percentage
            - flagMismatchedValues: Flag mismatched values percentage
        """
        compare_ground_truth = await self.compare_extracted_text_with_ground_truth_scorer.calculate_score(
            response, ground_truth, judge_platform_id, use_llm=use_llm
        )
        detect_errors = await self.detect_extraction_errors_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        flag_mismatched = await self.flag_mismatched_values_scorer.calculate_score(
            response, ground_truth, judge_platform_id, use_llm=use_llm
        )
        
        return DataExtractionAccuracySubScore(
            compareExtractedTextWithGroundTruth=compare_ground_truth,
            detectExtractionErrors=detect_errors,
            flagMismatchedValues=flag_mismatched,
        )

    # Legacy method names for backward compatibility
    async def calculate_compare_extracted_text_with_ground_truth(
        self, response: str, ground_truth: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate compare extracted text with ground truth percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            ground_truth: Ground truth text for comparison (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Compare extracted text with ground truth percentage (0-100)
        """
        return await self.compare_extracted_text_with_ground_truth_scorer.calculate_score(
            response, ground_truth, judge_platform_id, use_llm=use_llm
        )

    async def calculate_detect_extraction_errors(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate detect extraction errors percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Detect extraction errors percentage (0-100)
        """
        return await self.detect_extraction_errors_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_flag_mismatched_values(
        self, response: str, ground_truth: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate flag mismatched values percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            ground_truth: Ground truth text for comparison (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Flag mismatched values percentage (0-100)
        """
        return await self.flag_mismatched_values_scorer.calculate_score(
            response, ground_truth, judge_platform_id, use_llm=use_llm
        )

