"""Compare extracted text with ground truth score calculation for data extraction accuracy detection."""
from __future__ import annotations

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.data_extraction_accuracy.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class CompareExtractedTextWithGroundTruthScorer:
    """Calculates compare extracted text with ground truth percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize compare extracted text with ground truth scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, ground_truth: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate compare extracted text with ground truth percentage (0-100).
        
        Args:
            response: The response text to evaluate
            ground_truth: Ground truth text for comparison (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Compare extracted text with ground truth percentage (0-100)
        """
        if not ground_truth:
            # No ground truth available, assume high accuracy
            return 100.0
        
        # Simple word-based comparison
        response_words = set(response.lower().split())
        ground_truth_words = set(ground_truth.lower().split())
        
        if not ground_truth_words:
            return 100.0
        
        # Calculate overlap
        intersection = len(response_words & ground_truth_words)
        base_percentage = (intersection / len(ground_truth_words)) * 100
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Compare extracted text with ground truth and calculate accuracy (0-100%):

Ground Truth: {ground_truth[:500]}
Extracted Text: {response[:2000]}

Return ONLY JSON: {{"accuracy": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "accuracy", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

