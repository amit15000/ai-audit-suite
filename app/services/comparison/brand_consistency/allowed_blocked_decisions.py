"""Allowed/blocked decisions score calculation for brand consistency detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.brand_consistency.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class AllowedBlockedDecisionsScorer:
    """Calculates allowed/blocked decisions percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize allowed/blocked decisions scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate allowed/blocked decisions percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Allowed/blocked decisions percentage (0-100)
        """
        # Similar to agent action safety
        allowed_patterns = [
            r'\b(allowed|permitted|approved|authorized|granted)\b',
        ]
        
        blocked_patterns = [
            r'\b(blocked|denied|rejected|forbidden|prohibited)\b',
        ]
        
        allowed_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in allowed_patterns
        )
        
        blocked_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in blocked_patterns
        )
        
        total_decisions = allowed_count + blocked_count
        if total_decisions == 0:
            return 90.0  # Default high score
        
        base_percentage = (allowed_count / total_decisions) * 100
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the allowed/blocked decisions percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"allowedBlocked": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "allowedBlocked", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

