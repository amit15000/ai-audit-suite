"""Explainability score calculation for explainability detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.explainability.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class ExplainabilityScoreScorer:
    """Calculates explainability score percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize explainability score scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate explainability score percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Explainability score percentage (0-100)
        """
        # Check for explainability indicators
        explainability_patterns = [
            r'\b(explain|explanation|because|reason|why|how|therefore|thus)',
            r'\b(due\s+to|as\s+a\s+result|consequently|hence)',
            r'\b(step\s+by\s+step|detailed\s+explanation|clarification)',
            r'\b(example|illustration|demonstration|show)',
        ]
        
        explainability_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in explainability_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (explainability_count / word_count) * 100 * 10)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the explainability score percentage (0-100) for this response:

Response: {response[:2000]}

Return ONLY JSON: {{"explainabilityScore": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "explainabilityScore", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

