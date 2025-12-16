"""Brand-safe language score calculation for brand consistency detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.brand_consistency.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class BrandSafeLanguageScorer:
    """Calculates brand-safe language percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize brand-safe language scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate brand-safe language percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Brand-safe language percentage (0-100)
        """
        # Check for brand-unsafe language
        unsafe_patterns = [
            r'\b(curse|swear|profanity|offensive|inappropriate)',
            r'\b(controversial|polarizing|divisive)',
        ]
        
        unsafe_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in unsafe_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 100.0
        
        base_score = max(0.0, 100.0 - (unsafe_count / word_count) * 100 * 15)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the brand-safe language percentage (0-100) for this response:

Response: {response[:2000]}

Return ONLY JSON: {{"brandSafe": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_score = extract_json_float(judge_response, "brandSafe", base_score)
                base_score = base_score * 0.6 + llm_score * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_score)

