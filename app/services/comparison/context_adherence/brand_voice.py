"""Brand voice score calculation for context adherence detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.context_adherence.prompt_parser import PromptParser
from app.services.comparison.context_adherence.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    extract_json_explanation,
    clamp_percentage,
)


BRAND_VOICE_SYSTEM_PROMPT = """You are an expert brand voice evaluator assessing how well a response adheres to brand voice guidelines.

Your task is to:
1. Identify brand voice guidelines from the prompt (personality traits, style, tone, messaging)
2. Analyze the response for brand voice consistency
3. Evaluate adherence to brand personality and style
4. Calculate adherence percentage (0-100)

CRITICAL: You MUST return ONLY valid JSON. No other text before or after the JSON.

Return this exact JSON format:
{
    "brandVoice": <0-100>,
    "guidelines_found": "<brand voice guidelines or 'Not specified'>",
    "adherence_factors": ["factor1", "factor2", ...],
    "explanation": "<brief explanation of brand voice adherence>"
}

BRAND VOICE FACTORS TO EVALUATE:
- Personality traits (professional, friendly, innovative, authoritative, etc.)
- Tone consistency throughout the response
- Style and messaging alignment
- Use of brand-specific terminology
- Emotional tone and approach
- Communication style

SCORING GUIDELINES:
- 90-100: Perfect brand voice alignment, consistent throughout
- 70-89: Good brand voice alignment, mostly consistent
- 50-69: Moderate brand voice alignment, some inconsistencies
- 30-49: Poor brand voice alignment, significant deviations
- 0-29: Very poor brand voice alignment, major inconsistencies

If no brand voice guidelines are specified, evaluate based on:
- Tone consistency
- Style coherence
- Professional presentation"""


class BrandVoiceScorer:
    """Calculates brand voice adherence percentage using LLM-based analysis."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize brand voice scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service
        self.prompt_parser = PromptParser(ai_service)

    async def calculate_score(
        self, response: str, prompt: str = "", judge_platform_id: str = "openai", use_llm: bool = True
    ) -> tuple[float, str]:
        """Calculate brand voice adherence percentage using LLM analysis.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt (optional, may contain brand voice guidelines)
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM for evaluation (default: True)
            
        Returns:
            Tuple of (brand voice adherence percentage, explanation)
        """
        if not response or not response.strip():
            return 50.0, "Empty response - cannot evaluate brand voice"
        
        if use_llm:
            try:
                # Parse prompt to get brand voice guidelines
                brand_voice_guidelines = None
                if prompt:
                    parsed_prompt = await self.prompt_parser.parse_prompt(
                        prompt, judge_platform_id, use_llm=True
                    )
                    brand_voice_guidelines = parsed_prompt.brand_voice_guidelines
                
                # Build analysis prompt
                guidelines_text = brand_voice_guidelines if brand_voice_guidelines else "No specific brand voice guidelines specified in prompt"
                
                analysis_prompt = f"""Evaluate brand voice adherence of this response:

ORIGINAL PROMPT:
{prompt[:1000] if prompt else "Not provided"}

BRAND VOICE GUIDELINES:
{guidelines_text}

RESPONSE TO EVALUATE:
{response[:3000]}

Analyze:
1. Brand voice guidelines from the prompt (if specified)
2. Whether the response adheres to brand voice personality and style
3. Consistency of brand voice throughout the response
4. Calculate overall brand voice adherence percentage (0-100)

If no brand voice guidelines are specified, evaluate based on:
- Tone consistency
- Style coherence
- Professional presentation

Return ONLY valid JSON with the exact structure specified in the system prompt."""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id,
                    analysis_prompt,
                    system_prompt=BRAND_VOICE_SYSTEM_PROMPT,
                )
                
                # Extract brand voice score and explanation
                brand_voice_score = extract_json_float(judge_response, "brandVoice", 50.0)
                explanation = extract_json_explanation(
                    judge_response,
                    f"Brand voice adherence: {brand_voice_score:.1f}%. Response was evaluated against brand voice guidelines from the prompt."
                )
                return clamp_percentage(brand_voice_score), explanation
            except Exception as e:
                # Fallback to basic scoring
                score = self._calculate_basic_brand_score(response)
                return score, f"Basic brand voice scoring used due to error: {str(e)}"
        
        # Fallback to basic scoring
        score = self._calculate_basic_brand_score(response)
        return score, "Basic brand voice scoring used (LLM disabled)"
    
    def _calculate_basic_brand_score(self, response: str) -> float:
        """Basic brand voice scoring as fallback.
        
        Args:
            response: Response text
            
        Returns:
            Basic brand voice score (0-100)
        """
        response_lower = response.lower()
        brand_score = 0.0
        
        # Check for professional brand voice indicators
        brand_indicators = {
            'professional': ['professional', 'expert', 'quality', 'excellence', 'premium'],
            'friendly': ['friendly', 'welcoming', 'helpful', 'supportive', 'caring'],
            'innovative': ['innovative', 'cutting-edge', 'advanced', 'modern', 'forward-thinking'],
        }
        
        for category, keywords in brand_indicators.items():
            matches = sum(1 for keyword in keywords if keyword in response_lower)
            if matches > 0:
                brand_score += min(30, matches * 10)
        
        # Check for consistent tone throughout
        sentences = re.split(r'[.!?]+', response)
        if len(sentences) > 1:
            brand_score += 20
        
        return clamp_percentage(min(100.0, brand_score))

