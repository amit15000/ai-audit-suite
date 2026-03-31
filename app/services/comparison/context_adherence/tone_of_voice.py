"""Tone of voice score calculation for context adherence detection."""
from __future__ import annotations

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.context_adherence.prompt_parser import PromptParser
from app.services.comparison.context_adherence.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_string,
    extract_json_explanation,
)


TONE_DETECTION_SYSTEM_PROMPT = """You are an expert tone analyzer specializing in identifying the tone of voice in written text.

Your task is to:
1. Analyze the response text to determine its tone
2. Compare it against the required tone (if specified in prompt)
3. Return the detected tone

CRITICAL: You MUST return ONLY valid JSON. No other text before or after the JSON.

Return this exact JSON format:
{
    "tone": "<Professional|Casual|Formal|Friendly|Polite|Neutral|Other>",
    "confidence": <0-100>,
    "matches_requirement": <true|false>,
    "explanation": "<brief explanation>"
}

TONE CATEGORIES:
- Professional: Business-like, authoritative, objective
- Casual: Informal, relaxed, conversational
- Formal: Academic, ceremonial, very structured
- Friendly: Warm, approachable, welcoming
- Polite: Courteous, respectful, considerate
- Neutral: Balanced, neither formal nor casual
- Other: If tone doesn't fit above categories, describe it

Consider:
- Word choice and vocabulary level
- Sentence structure and formality
- Use of contractions, slang, or technical terms
- Overall communication style"""


class ToneOfVoiceScorer:
    """Calculates tone of voice using LLM-based analysis."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize tone of voice scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service
        self.prompt_parser = PromptParser(ai_service)

    async def calculate_score(
        self, response: str, prompt: str = "", judge_platform_id: str = "openai", use_llm: bool = True
    ) -> tuple[str, str]:
        """Calculate tone of voice using LLM analysis.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt (optional, to check tone requirement)
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM for evaluation (default: True)
            
        Returns:
            Tuple of (tone of voice string, explanation)
        """
        if not response or not response.strip():
            return "Neutral", "Empty response - defaulting to Neutral tone"
        
        if use_llm:
            try:
                # Parse prompt to get tone requirement
                required_tone = None
                if prompt:
                    parsed_prompt = await self.prompt_parser.parse_prompt(
                        prompt, judge_platform_id, use_llm=True
                    )
                    required_tone = parsed_prompt.tone_requirement
                
                # Build analysis prompt
                tone_requirement_text = f"\nREQUIRED TONE: {required_tone}" if required_tone else "\nREQUIRED TONE: Not specified"
                
                analysis_prompt = f"""Analyze the tone of voice in this response:

ORIGINAL PROMPT (if provided):
{prompt[:1000] if prompt else "Not provided"}
{tone_requirement_text}

RESPONSE TO ANALYZE:
{response[:3000]}

Determine:
1. The tone of voice in the response
2. Whether it matches the required tone (if specified)
3. Confidence level in the tone assessment

Return ONLY valid JSON with the exact structure specified in the system prompt."""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id,
                    analysis_prompt,
                    system_prompt=TONE_DETECTION_SYSTEM_PROMPT,
                )
                
                # Extract tone and explanation
                detected_tone = extract_json_string(judge_response, "tone", "Neutral")
                explanation = extract_json_explanation(
                    judge_response,
                    f"Tone detected: {detected_tone}. Response was analyzed for tone of voice characteristics."
                )
                
                # Capitalize first letter
                if detected_tone:
                    detected_tone = detected_tone.capitalize()
                    # Map common variations
                    tone_mapping = {
                        "Professional": "Professional",
                        "Casual": "Casual",
                        "Formal": "Formal",
                        "Friendly": "Friendly",
                        "Polite": "Polite",
                        "Neutral": "Neutral",
                    }
                    for key, value in tone_mapping.items():
                        if key.lower() in detected_tone.lower():
                            return value, explanation
                    return detected_tone, explanation
                return "Neutral", explanation
            except Exception as e:
                # Fallback to basic pattern matching
                tone = self._detect_basic_tone(response)
                return tone, f"Basic tone detection used due to error: {str(e)}"
        
        # Fallback to basic pattern matching
        tone = self._detect_basic_tone(response)
        return tone, "Basic tone detection used (LLM disabled)"
    
    def _detect_basic_tone(self, response: str) -> str:
        """Basic pattern-based tone detection as fallback.
        
        Args:
            response: Response text
            
        Returns:
            Detected tone string
        """
        response_lower = response.lower()
        
        polite_indicators = ['please', 'thank you', 'appreciate', 'kindly', 'respectfully']
        professional_indicators = ['according to', 'based on', 'analysis', 'research', 'data', 'evidence']
        casual_indicators = ['hey', 'yeah', 'gonna', 'wanna', 'cool', 'awesome', 'lol']
        formal_indicators = ['therefore', 'furthermore', 'consequently', 'moreover', 'thus']
        
        polite_count = sum(1 for indicator in polite_indicators if indicator in response_lower)
        professional_count = sum(1 for indicator in professional_indicators if indicator in response_lower)
        casual_count = sum(1 for indicator in casual_indicators if indicator in response_lower)
        formal_count = sum(1 for indicator in formal_indicators if indicator in response_lower)
        
        if polite_count > professional_count and polite_count > casual_count:
            return "Polite"
        elif professional_count > casual_count:
            return "Professional"
        elif casual_count > 0:
            return "Casual"
        elif formal_count > 0:
            return "Formal"
        else:
            return "Neutral"

