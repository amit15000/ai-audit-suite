"""Format rules score calculation for context adherence detection."""
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


FORMAT_ADHERENCE_SYSTEM_PROMPT = """You are an expert format evaluator assessing how well a response adheres to format requirements specified in a prompt.

Your task is to:
1. Identify format requirements from the prompt (markdown, JSON, bullet points, tables, etc.)
2. Analyze the response structure and formatting
3. Check if format requirements are met
4. Calculate adherence percentage (0-100)

CRITICAL: You MUST return ONLY valid JSON. No other text before or after the JSON.

Return this exact JSON format:
{
    "formatAdherence": <0-100>,
    "requirements_found": ["requirement1", "requirement2", ...],
    "requirements_met": ["requirement1", ...],
    "requirements_missing": ["requirement1", ...],
    "explanation": "<brief explanation of format adherence>"
}

FORMAT TYPES TO CHECK:
- Markdown formatting (headings, bold, italic, lists)
- JSON structure
- Bullet points or numbered lists
- Tables
- Code blocks
- Paragraph structure
- Headings and sections
- Other structural elements

SCORING GUIDELINES:
- 90-100: All format requirements perfectly met
- 70-89: Most requirements met, minor issues
- 50-69: Some requirements met, significant gaps
- 30-49: Few requirements met, major issues
- 0-29: Almost no format requirements met"""


class FormatRulesScorer:
    """Calculates format rules adherence percentage using LLM-based analysis."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize format rules scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service
        self.prompt_parser = PromptParser(ai_service)

    async def calculate_score(
        self, response: str, prompt: str, judge_platform_id: str = "openai", use_llm: bool = True
    ) -> tuple[float, str]:
        """Calculate format rules adherence percentage using LLM analysis.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM for evaluation (default: True)
            
        Returns:
            Tuple of (format adherence percentage, explanation)
        """
        if not response or not response.strip():
            return 0.0, "Empty response - no format can be evaluated"
        
        if use_llm:
            try:
                # Parse prompt to get format requirements
                format_requirements = []
                if prompt:
                    parsed_prompt = await self.prompt_parser.parse_prompt(
                        prompt, judge_platform_id, use_llm=True
                    )
                    format_requirements = parsed_prompt.format_requirements
                
                # Build analysis prompt
                format_reqs_text = "\n".join([f"- {req}" for req in format_requirements]) if format_requirements else "No specific format requirements extracted"
                
                analysis_prompt = f"""Evaluate format adherence of this response:

ORIGINAL PROMPT:
{prompt[:1000] if prompt else "Not provided"}

FORMAT REQUIREMENTS EXTRACTED:
{format_reqs_text}

RESPONSE TO EVALUATE:
{response[:3000]}

Analyze:
1. All format requirements from the prompt (explicit and implicit)
2. Whether each requirement is met in the response
3. Calculate overall format adherence percentage (0-100)
4. List any missing format requirements

Return ONLY valid JSON with the exact structure specified in the system prompt."""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id,
                    analysis_prompt,
                    system_prompt=FORMAT_ADHERENCE_SYSTEM_PROMPT,
                )
                
                # Extract adherence score and explanation
                adherence_score = extract_json_float(judge_response, "formatAdherence", 50.0)
                explanation = extract_json_explanation(
                    judge_response,
                    f"Format adherence: {adherence_score:.1f}%. Response was evaluated against format requirements from the prompt."
                )
                return clamp_percentage(adherence_score), explanation
            except Exception as e:
                # Fallback to basic format checking
                score = self._calculate_basic_format_score(response)
                return score, f"Basic format scoring used due to error: {str(e)}"
        
        # Fallback to basic format checking
        score = self._calculate_basic_format_score(response)
        return score, "Basic format scoring used (LLM disabled)"
    
    def _calculate_basic_format_score(self, response: str) -> float:
        """Basic format checking as fallback.
        
        Args:
            response: Response text
            
        Returns:
            Basic format score (0-100)
        """
        format_score = 0.0
        
        # Check if response has structure
        has_structure = bool(re.search(r'\n\n', response)) or bool(re.search(r'^[\s]*[-*•]', response, re.MULTILINE))
        if has_structure:
            format_score += 20
        
        # Check for proper punctuation
        has_punctuation = bool(re.search(r'[.!?]$', response.strip()))
        if has_punctuation:
            format_score += 20
        
        # Check for capitalization
        has_capitalization = bool(re.search(r'^[A-Z]', response.strip()))
        if has_capitalization:
            format_score += 20
        
        # Check for consistent formatting
        has_consistent_format = len(set(re.findall(r'\n', response))) <= 2
        if has_consistent_format:
            format_score += 20
        
        # Check for no excessive whitespace
        no_excessive_whitespace = not bool(re.search(r'\s{3,}', response))
        if no_excessive_whitespace:
            format_score += 20
        
        return clamp_percentage(format_score)

