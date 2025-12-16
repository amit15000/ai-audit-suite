"""Flag mismatched values score calculation for data extraction accuracy detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.data_extraction_accuracy.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class FlagMismatchedValuesScorer:
    """Calculates flag mismatched values percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize flag mismatched values scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, ground_truth: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate flag mismatched values percentage (0-100).
        
        Args:
            response: The response text to evaluate
            ground_truth: Ground truth text for comparison (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Flag mismatched values percentage (0-100)
        """
        if not ground_truth:
            return 0.0
        
        # Extract numbers and key values
        response_numbers = set(re.findall(r'\b\d+\.?\d*\b', response))
        ground_truth_numbers = set(re.findall(r'\b\d+\.?\d*\b', ground_truth))
        
        if not ground_truth_numbers:
            return 0.0
        
        # Find mismatches
        mismatches = ground_truth_numbers - response_numbers
        mismatch_percentage = (len(mismatches) / len(ground_truth_numbers)) * 100 if ground_truth_numbers else 0.0
        
        base_percentage = min(100.0, mismatch_percentage * 10)  # Scale up
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the mismatched values percentage (0-100) between ground truth and extracted text:

Ground Truth: {ground_truth[:500]}
Extracted Text: {response[:2000]}

Return ONLY JSON: {{"mismatchedValues": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "mismatchedValues", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

