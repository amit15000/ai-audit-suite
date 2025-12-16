"""Format score calculation for brand consistency detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.brand_consistency.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class FormatScorer:
    """Calculates format consistency percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize format scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate format consistency percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Format consistency percentage (0-100)
        """
        # Check for format consistency
        has_consistent_format = bool(re.search(r'\n\n', response)) or bool(re.search(r'^[\s]*[-*•]', response, re.MULTILINE))
        base_score = 100.0 if has_consistent_format else 90.0
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the format consistency percentage (0-100) for this response:

Response: {response[:2000]}

Return ONLY JSON: {{"format": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_score = extract_json_float(judge_response, "format", base_score)
                base_score = base_score * 0.6 + llm_score * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_score)

