"""Model scoring score calculation for multi-judge AI review detection."""
from __future__ import annotations

import re
from typing import Dict

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.multi_judge_ai_review.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class ModelScoringScorer:
    """Calculates model scoring percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize model scoring scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, all_responses: Dict[str, str], judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate model scoring percentage (0-100).
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Model scoring percentage (0-100)
        """
        # Check for scoring indicators
        scoring_patterns = [
            r'\b(score|rating|evaluation|assessment|grade)\s+(of|is|:)\s*\d+',
            r'\b(rated|scored|evaluated|assessed)\s+(at|as|with)\s*\d+',
        ]
        
        scoring_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in scoring_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (scoring_count / word_count) * 100 * 20)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the model scoring percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"modelScoring": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "modelScoring", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

