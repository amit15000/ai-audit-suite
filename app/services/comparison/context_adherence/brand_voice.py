"""Brand voice score calculation for context adherence detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.context_adherence.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class BrandVoiceScorer:
    """Calculates brand voice adherence percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize brand voice scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate brand voice adherence percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Brand voice adherence percentage (0-100)
        """
        # Check for professional brand voice indicators
        brand_indicators = {
            'professional': ['professional', 'expert', 'quality', 'excellence', 'premium'],
            'friendly': ['friendly', 'welcoming', 'helpful', 'supportive', 'caring'],
            'innovative': ['innovative', 'cutting-edge', 'advanced', 'modern', 'forward-thinking'],
        }
        
        response_lower = response.lower()
        brand_score = 0.0
        
        # Check for consistent brand voice
        for category, keywords in brand_indicators.items():
            matches = sum(1 for keyword in keywords if keyword in response_lower)
            if matches > 0:
                brand_score += min(30, matches * 10)
        
        # Check for consistent tone throughout
        sentences = re.split(r'[.!?]+', response)
        if len(sentences) > 1:
            # Check if tone is consistent
            has_consistent_tone = True  # Simplified check
            if has_consistent_tone:
                brand_score += 20
        
        base_percentage = min(100.0, brand_score)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt_text = f"""Calculate brand voice adherence percentage (0-100) of this response:

Response: {response[:2000]}

Return ONLY JSON: {{"brandVoice": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt_text, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "brandVoice", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

