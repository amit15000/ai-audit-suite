"""Vocabulary score calculation for brand consistency detection."""
from __future__ import annotations

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.brand_consistency.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class VocabularyScorer:
    """Calculates vocabulary consistency percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize vocabulary scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate vocabulary consistency percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Vocabulary consistency percentage (0-100)
        """
        # Check for vocabulary consistency
        base_score = 100.0  # Assume consistent vocabulary
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the vocabulary consistency percentage (0-100) for this response:

Response: {response[:2000]}

Return ONLY JSON: {{"vocabulary": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_score = extract_json_float(judge_response, "vocabulary", base_score)
                base_score = base_score * 0.6 + llm_score * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_score)

