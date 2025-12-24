"""Length constraints score calculation for context adherence detection."""
from __future__ import annotations

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.context_adherence.prompt_parser import PromptParser
from app.services.comparison.context_adherence.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_string,
    extract_json_explanation,
)


LENGTH_CONSTRAINTS_SYSTEM_PROMPT = """You are an expert evaluator assessing whether a response meets length constraints specified in a prompt.

Your task is to:
1. Identify length requirements from the prompt (word count, character count, or category)
2. Measure the actual response length
3. Determine if the response meets the requirements
4. Classify the response length category

CRITICAL: You MUST return ONLY valid JSON. No other text before or after the JSON.

Return this exact JSON format:
{
    "length": "<Short|Medium|Long|Very Long>",
    "word_count": <number>,
    "meets_requirement": <true|false>,
    "requirement": "<extracted requirement or 'Not specified'>",
    "explanation": "<brief explanation>"
}

LENGTH CATEGORIES:
- Short: < 100 words
- Medium: 100-300 words
- Long: 300-800 words
- Very Long: > 800 words

Consider:
- Explicit word/character counts (e.g., "200 words", "under 500 characters")
- Length categories (e.g., "brief", "short", "detailed", "comprehensive")
- Context and purpose (some topics require more length)"""


class LengthConstraintsScorer:
    """Calculates length constraints adherence using LLM-based analysis."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize length constraints scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service
        self.prompt_parser = PromptParser(ai_service)

    async def calculate_score(
        self, response: str, prompt: str, judge_platform_id: str = "openai", use_llm: bool = True
    ) -> tuple[str, str]:
        """Calculate length constraints adherence using LLM analysis.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM for evaluation (default: True)
            
        Returns:
            Tuple of (length category string, explanation)
        """
        if not response or not response.strip():
            return "Short", "Empty response - classified as Short"
        
        word_count = len(response.split())
        char_count = len(response)
        
        if use_llm:
            try:
                # Parse prompt to get length constraint
                length_constraint = None
                if prompt:
                    parsed_prompt = await self.prompt_parser.parse_prompt(
                        prompt, judge_platform_id, use_llm=True
                    )
                    length_constraint = parsed_prompt.length_constraint
                
                # Build analysis prompt
                constraint_text = ""
                if length_constraint:
                    min_words = length_constraint.get("min_words")
                    max_words = length_constraint.get("max_words")
                    category = length_constraint.get("category", "Not specified")
                    explicit = length_constraint.get("explicit_requirement", "")
                    
                    constraint_text = f"""
LENGTH REQUIREMENT FROM PROMPT:
- Category: {category}
- Min words: {min_words if min_words else 'Not specified'}
- Max words: {max_words if max_words else 'Not specified'}
- Explicit requirement: {explicit if explicit else 'Not specified'}"""
                else:
                    constraint_text = "\nLENGTH REQUIREMENT: Not specified in prompt"
                
                analysis_prompt = f"""Evaluate if this response meets length constraints:

ORIGINAL PROMPT:
{prompt[:1000] if prompt else "Not provided"}
{constraint_text}

RESPONSE TO EVALUATE:
- Word count: {word_count}
- Character count: {char_count}
- Response preview: {response[:500]}...

Determine:
1. The length category of the response
2. Whether it meets the length requirement (if specified)
3. If requirement is not specified, classify based on standard categories

Return ONLY valid JSON with the exact structure specified in the system prompt."""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id,
                    analysis_prompt,
                    system_prompt=LENGTH_CONSTRAINTS_SYSTEM_PROMPT,
                )
                
                # Extract length category and explanation
                length_category = extract_json_string(judge_response, "length", None)
                explanation = extract_json_explanation(
                    judge_response,
                    f"Length category: {length_category or 'Unknown'}. Response has {word_count} words and {char_count} characters."
                )
                
                if length_category:
                    # Normalize to standard categories
                    length_lower = length_category.lower()
                    if "short" in length_lower or "brief" in length_lower:
                        return "Short", explanation
                    elif "medium" in length_lower:
                        return "Medium", explanation
                    elif "long" in length_lower and "very" not in length_lower:
                        return "Long", explanation
                    elif "very long" in length_lower or "very" in length_lower:
                        return "Very Long", explanation
                    else:
                        return length_category.capitalize(), explanation
                return "Medium", explanation
            except Exception as e:
                # Fallback to basic word count classification
                length = self._classify_basic_length(word_count)
                return length, f"Basic length classification used due to error: {str(e)}"
        
        # Fallback to basic word count classification
        length = self._classify_basic_length(word_count)
        return length, f"Basic length classification used (LLM disabled). Response has {word_count} words."
    
    def _classify_basic_length(self, word_count: int) -> str:
        """Basic word count-based classification as fallback.
        
        Args:
            word_count: Number of words in response
            
        Returns:
            Length category string
        """
        if word_count < 50:
            return "Short"
        elif word_count < 200:
            return "Medium"
        elif word_count < 500:
            return "Long"
        else:
            return "Very Long"

