"""Copied news articles score calculation for AI plagiarism detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.ai_plagiarism.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class CopiedNewsArticlesScorer:
    """Calculates copied news articles percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize copied news articles scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied news articles percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Copied news articles percentage (0-100)
        """
        # Check for news article indicators
        news_patterns = [
            r'\b(news\s+article|news\s+report|breaking\s+news|headline)',
            r'\b(published\s+in|reported\s+by|according\s+to\s+news)',
            r'\b(journalist|reporter|news\s+source)',
        ]
        
        news_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in news_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (news_count / word_count) * 100 * 15)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the copied news articles percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"copiedNews": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "copiedNews", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

