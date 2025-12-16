"""Copied books score calculation for AI plagiarism detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.ai_plagiarism.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class CopiedBooksScorer:
    """Calculates copied books percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize copied books scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied books percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Copied books percentage (0-100)
        """
        # Check for book indicators
        book_patterns = [
            r'\b(book|novel|textbook|publication|author\s+wrote)',
            r'\b(chapter\s+\d+|page\s+\d+|published\s+in\s+\d{4})',
            r'\b(isbn|publisher|edition)',
        ]
        
        book_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in book_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (book_count / word_count) * 100 * 20)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the copied books percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"copiedBooks": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "copiedBooks", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

