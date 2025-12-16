"""Length constraints score calculation for context adherence detection."""
from __future__ import annotations

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.context_adherence.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_string,
)


class LengthConstraintsScorer:
    """Calculates length constraints adherence."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize length constraints scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, prompt: str, judge_platform_id: str, use_llm: bool = False
    ) -> str:
        """Calculate length constraints adherence (e.g., 'Short', 'Medium', 'Long').
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Length constraints string (e.g., 'Short', 'Medium', 'Long', 'Very Long')
        """
        word_count = len(response.split())
        
        # Determine length category
        if word_count < 50:
            base_length = "Short"
        elif word_count < 200:
            base_length = "Medium"
        elif word_count < 500:
            base_length = "Long"
        else:
            base_length = "Very Long"
        
        # Check if prompt specifies length requirements
        if prompt:
            prompt_lower = prompt.lower()
            if any(word in prompt_lower for word in ['short', 'brief', 'concise']):
                if word_count > 100:
                    base_length = "Long"  # Doesn't meet short requirement
            elif any(word in prompt_lower for word in ['long', 'detailed', 'comprehensive', 'extensive']):
                if word_count < 200:
                    base_length = "Short"  # Doesn't meet long requirement
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt_text = f"""Determine if this response meets length constraints (Short, Medium, Long):

Prompt: {prompt[:500] if prompt else 'No specific length requirement'}
Response length: {word_count} words

Return ONLY JSON: {{"length": "<Short/Medium/Long>", "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt_text, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_length = extract_json_string(judge_response, "length", base_length)
                if llm_length:
                    base_length = llm_length
            except Exception:
                pass
        
        return base_length

