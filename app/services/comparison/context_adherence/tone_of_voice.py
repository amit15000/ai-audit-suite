"""Tone of voice score calculation for context adherence detection."""
from __future__ import annotations

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.context_adherence.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_string,
)


class ToneOfVoiceScorer:
    """Calculates tone of voice."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize tone of voice scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> str:
        """Calculate tone of voice (e.g., 'Polite', 'Professional', 'Casual').
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Tone of voice string (e.g., 'Polite', 'Professional', 'Casual', 'Formal', 'Neutral')
        """
        # Tone indicators
        polite_indicators = ['please', 'thank you', 'appreciate', 'kindly', 'respectfully']
        professional_indicators = ['according to', 'based on', 'analysis', 'research', 'data', 'evidence']
        casual_indicators = ['hey', 'yeah', 'gonna', 'wanna', 'cool', 'awesome', 'lol']
        formal_indicators = ['therefore', 'furthermore', 'consequently', 'moreover', 'thus']
        
        response_lower = response.lower()
        
        polite_count = sum(1 for indicator in polite_indicators if indicator in response_lower)
        professional_count = sum(1 for indicator in professional_indicators if indicator in response_lower)
        casual_count = sum(1 for indicator in casual_indicators if indicator in response_lower)
        formal_count = sum(1 for indicator in formal_indicators if indicator in response_lower)
        
        # Determine tone based on highest count
        if polite_count > professional_count and polite_count > casual_count:
            base_tone = "Polite"
        elif professional_count > casual_count:
            base_tone = "Professional"
        elif casual_count > 0:
            base_tone = "Casual"
        elif formal_count > 0:
            base_tone = "Formal"
        else:
            base_tone = "Neutral"
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt_text = f"""Determine the tone of voice of this response (Polite, Professional, Casual, Formal, Neutral):

Response: {response[:2000]}

Return ONLY JSON: {{"tone": "<tone>", "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt_text, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_tone = extract_json_string(judge_response, "tone", base_tone)
                if llm_tone:
                    base_tone = llm_tone
            except Exception:
                pass
        
        return base_tone

