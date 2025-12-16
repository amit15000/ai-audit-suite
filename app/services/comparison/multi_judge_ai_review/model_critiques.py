"""Model critiques score calculation for multi-judge AI review detection."""
from __future__ import annotations

import re
from typing import Dict

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.multi_judge_ai_review.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class ModelCritiquesScorer:
    """Calculates model critiques percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize model critiques scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, all_responses: Dict[str, str], judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate model critiques percentage (0-100).
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Model critiques percentage (0-100)
        """
        # Check for critique indicators
        critique_patterns = [
            r'\b(critique|criticism|feedback|review|analysis|evaluation)',
            r'\b(weakness|strength|improvement|suggestion|recommendation)',
            r'\b(positive|negative|good|bad|excellent|poor)\s+(aspect|point|feature)',
        ]
        
        critique_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in critique_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (critique_count / word_count) * 100 * 15)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the model critiques percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"modelCritiques": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "modelCritiques", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

