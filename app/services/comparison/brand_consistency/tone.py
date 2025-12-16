"""Tone score calculation for brand consistency detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.brand_consistency.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class ToneScorer:
    """Calculates tone consistency percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize tone scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate tone consistency percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Tone consistency percentage (0-100)
        """
        # Check for consistent tone indicators
        tone_indicators = ['professional', 'friendly', 'formal', 'casual', 'polite']
        tone_count = sum(1 for indicator in tone_indicators if indicator in response.lower())
        
        # Check for tone inconsistencies
        inconsistent_patterns = [
            r'\b(very\s+formal.*very\s+casual|casual.*formal)',
            r'\b(polite.*rude|professional.*unprofessional)',
        ]
        
        inconsistent_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in inconsistent_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 100.0
        
        base_score = 100.0 - min(100.0, (inconsistent_count / word_count) * 100 * 20)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the tone consistency percentage (0-100) for this response:

Response: {response[:2000]}

Return ONLY JSON: {{"tone": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_score = extract_json_float(judge_response, "tone", base_score)
                base_score = base_score * 0.6 + llm_score * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_score)

