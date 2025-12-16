"""Copied sentences score calculation for explainability detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.explainability.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class CopiedSentencesScorer:
    """Calculates copied sentences percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize copied sentences scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied sentences percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Copied sentences percentage (0-100)
        """
        # Similar to plagiarism checker
        sentences = re.split(r'[.!?]+', response)
        total_sentences = len([s for s in sentences if s.strip()])
        
        if total_sentences == 0:
            return 0.0
        
        # Check for common phrases that might indicate copying
        common_phrases = [
            r'\b(as\s+stated\s+in|according\s+to\s+the|as\s+reported\s+by)',
            r'\b(the\s+following\s+is\s+an\s+excerpt|quoted\s+from)',
        ]
        
        copied_indicators = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in common_phrases
        )
        
        base_percentage = min(100.0, (copied_indicators / total_sentences) * 100 * 10)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the copied sentences percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"copiedSentences": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "copiedSentences", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

