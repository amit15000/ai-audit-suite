"""All instructions score calculation for context adherence detection."""
from __future__ import annotations

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.context_adherence.prompt_parser import PromptParser
from app.services.comparison.context_adherence.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    extract_json_explanation,
    clamp_percentage,
)


INSTRUCTIONS_ADHERENCE_SYSTEM_PROMPT = """You are an expert evaluator assessing how well a response adheres to all instructions from a prompt.

Your task is to:
1. Identify ALL instructions from the prompt (explicit and implicit)
2. Check if each instruction is followed in the response
3. Calculate adherence percentage based on instructions followed vs. total instructions

CRITICAL: You MUST return ONLY valid JSON. No other text before or after the JSON.

Return this exact JSON format:
{
    "adherence": <0-100>,
    "instructions_found": <number>,
    "instructions_followed": <number>,
    "missing_instructions": ["instruction1", "instruction2", ...],
    "explanation": "<brief explanation of adherence assessment>"
}

SCORING GUIDELINES:
- 90-100: All or nearly all instructions followed perfectly
- 70-89: Most instructions followed, minor gaps
- 50-69: Some instructions followed, significant gaps
- 30-49: Few instructions followed, major gaps
- 0-29: Almost no instructions followed

Consider:
- Explicit instructions (e.g., "use bullet points", "include examples")
- Implicit instructions (e.g., "explain X" implies providing explanation)
- Quality of instruction fulfillment (partially vs. fully)
- Critical vs. minor instructions"""


class AllInstructionsScorer:
    """Calculates all instructions adherence percentage using LLM-based analysis."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize all instructions scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service
        self.prompt_parser = PromptParser(ai_service)

    async def calculate_score(
        self, response: str, prompt: str, judge_platform_id: str, use_llm: bool = True
    ) -> tuple[float, str]:
        """Calculate all instructions adherence percentage (0-100) using LLM analysis.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM for evaluation (default: True)
            
        Returns:
            Tuple of (adherence percentage, explanation)
        """
        # If no prompt provided, assume high adherence
        if not prompt or not prompt.strip():
            return 95.0, "No prompt provided - assuming high adherence"
        
        if not response or not response.strip():
            return 0.0, "Empty response - no instructions can be followed"
        
        # Use LLM to parse prompt and analyze response
        if use_llm:
            try:
                # Parse prompt to extract instructions
                parsed_prompt = await self.prompt_parser.parse_prompt(
                    prompt, judge_platform_id, use_llm=True
                )
                
                # Build analysis prompt
                instructions_list = "\n".join([f"- {inst}" for inst in parsed_prompt.instructions])
                if not instructions_list:
                    instructions_list = "Analyze the prompt to identify all instructions"
                
                analysis_prompt = f"""Analyze how well this response adheres to ALL instructions from the prompt.

ORIGINAL PROMPT:
{prompt[:2000]}

EXTRACTED INSTRUCTIONS:
{instructions_list}

RESPONSE TO EVALUATE:
{response[:3000]}

Evaluate:
1. Identify ALL instructions from the prompt (both explicit and implicit)
2. Check if each instruction is followed in the response
3. Calculate adherence percentage (0-100)
4. List any missing or unfollowed instructions

Return ONLY valid JSON with the exact structure specified in the system prompt."""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id,
                    analysis_prompt,
                    system_prompt=INSTRUCTIONS_ADHERENCE_SYSTEM_PROMPT,
                )
                
                # Extract adherence score and explanation
                adherence_score = extract_json_float(judge_response, "adherence", 50.0)
                explanation = extract_json_explanation(
                    judge_response,
                    f"Instructions adherence: {adherence_score:.1f}%. Response was evaluated against all instructions from the prompt."
                )
                return clamp_percentage(adherence_score), explanation
            except Exception as e:
                # Fallback to basic keyword matching
                score = self._calculate_basic_score(response, prompt)
                return score, f"Basic scoring used due to error: {str(e)}"
        
        # Fallback to basic scoring
        score = self._calculate_basic_score(response, prompt)
        return score, "Basic keyword-based scoring used (LLM disabled)"
    
    def _calculate_basic_score(self, response: str, prompt: str) -> float:
        """Basic keyword-based scoring as fallback.
        
        Args:
            response: Response text
            prompt: Original prompt
            
        Returns:
            Basic adherence percentage
        """
        prompt_words = set(prompt.lower().split())
        response_words = set(response.lower().split())
        
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        prompt_keywords = prompt_words - stop_words
        response_keywords = response_words - stop_words
        
        if len(prompt_keywords) == 0:
            return 95.0
        
        overlap = len(prompt_keywords & response_keywords)
        base_percentage = (overlap / len(prompt_keywords)) * 100
        
        return clamp_percentage(base_percentage)

