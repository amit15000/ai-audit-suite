"""Copied copyrighted text score calculation for AI plagiarism detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.ai_plagiarism.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class CopiedCopyrightedTextScorer:
    """Calculates copied copyrighted text percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize copied copyrighted text scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied copyrighted text percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Copied copyrighted text percentage (0-100)
        """
        # Check for copyright indicators
        copyright_patterns = [
            r'\b(copyright|©|\(c\)|all\s+rights\s+reserved)',
            r'\b(proprietary|confidential|intellectual\s+property)',
            r'\b(unauthorized\s+use|copyrighted\s+material)',
        ]
        
        copyright_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in copyright_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (copyright_count / word_count) * 100 * 25)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the copied copyrighted text percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"copiedCopyrighted": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "copiedCopyrighted", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

