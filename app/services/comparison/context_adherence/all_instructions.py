"""All instructions score calculation for context adherence detection."""
from __future__ import annotations

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.context_adherence.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class AllInstructionsScorer:
    """Calculates all instructions adherence percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize all instructions scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, prompt: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate all instructions adherence percentage (0-100).
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            All instructions adherence percentage (0-100)
        """
        # If no prompt provided, assume high adherence
        if not prompt:
            return 95.0
        
        # Check if response addresses key terms from prompt
        prompt_words = set(prompt.lower().split())
        response_words = set(response.lower().split())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        prompt_keywords = prompt_words - stop_words
        response_keywords = response_words - stop_words
        
        if len(prompt_keywords) == 0:
            return 95.0
        
        # Calculate keyword overlap
        overlap = len(prompt_keywords & response_keywords)
        base_percentage = (overlap / len(prompt_keywords)) * 100
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt_text = f"""Calculate how well this response adheres to all instructions (0-100%):

Prompt: {prompt[:500]}
Response: {response[:2000]}

Return ONLY JSON: {{"adherence": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt_text, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "adherence", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

