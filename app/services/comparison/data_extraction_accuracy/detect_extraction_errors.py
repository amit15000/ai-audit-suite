"""Detect extraction errors score calculation for data extraction accuracy detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.data_extraction_accuracy.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class DetectExtractionErrorsScorer:
    """Calculates detect extraction errors percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize detect extraction errors scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate detect extraction errors percentage (0-100).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Detect extraction errors percentage (0-100)
        """
        # Error detection patterns
        error_patterns = [
            r'\b(error|mistake|incorrect|wrong|invalid|failed|failure)',
            r'\b(missing\s+data|incomplete\s+extraction|partial\s+data)',
            r'\b(extraction\s+error|parsing\s+error|format\s+error)',
        ]
        
        error_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in error_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (error_count / word_count) * 100 * 30)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the extraction errors detected percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"extractionErrors": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "extractionErrors", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

