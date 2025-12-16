"""Style score calculation for brand consistency detection."""
from __future__ import annotations

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.brand_consistency.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class StyleScorer:
    """Calculates style consistency percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize style scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate style consistency percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Style consistency percentage (0-100)
        """
        # Check for style consistency
        style_indicators = ['consistent', 'uniform', 'standardized']
        style_count = sum(1 for indicator in style_indicators if indicator in response.lower())
        
        base_score = min(100.0, 100.0 - (style_count * 5))  # Lower is better for this metric
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the style consistency percentage (0-100) for this response:

Response: {response[:2000]}

Return ONLY JSON: {{"style": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_score = extract_json_float(judge_response, "style", base_score)
                base_score = base_score * 0.6 + llm_score * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_score)

