"""Step-by-step reasoning detection for reasoning quality scoring."""
from __future__ import annotations

import asyncio
import json
import os
import re

from openai import OpenAI

from app.services.comparison.reasoning_quality.utils import (
    extract_json_score,
    clamp_score,
)
from app.services.llm.ai_platform_service import AIPlatformService


STEP_BY_STEP_REASONING_SYSTEM_PROMPT = """You are an expert evaluator specializing in analyzing step-by-step reasoning quality in written responses.

Your expertise lies in identifying whether responses demonstrate:
- Clear, structured logical progression
- Explicit reasoning steps with proper transitions
- Well-organized argument flow
- Logical connectors and causal relationships

CORE PRINCIPLES:
1. **Step-by-Step Structure**: Responses should show clear progression from premises to conclusions
2. **Logical Flow**: Each step should logically follow from the previous one
3. **Explicit Reasoning**: Reasoning should be clearly articulated, not implicit
4. **Proper Transitions**: Steps should be connected with appropriate logical connectors

WHAT TO LOOK FOR:

POSITIVE INDICATORS (High Score):
- Clear enumeration of steps (first, second, third, etc.)
- Explicit logical connectors (therefore, because, thus, consequently, hence, as a result)
- Structured progression from premises to conclusions
- Clear cause-and-effect relationships
- Methodical breakdown of complex problems
- Sequential reasoning patterns
- Well-organized argument structure

NEGATIVE INDICATORS (Low Score):
- Abrupt jumps in reasoning without explanation
- Missing logical connections between statements
- Lack of explicit reasoning steps
- Unclear progression from one idea to the next
- Implicit reasoning that is not clearly stated
- Disorganized flow of ideas

SCORING GUIDELINES:
- 10: Excellent step-by-step reasoning with clear structure and explicit logical flow
- 8-9: Good step-by-step reasoning with mostly clear structure
- 6-7: Moderate step-by-step reasoning, some structure present but could be clearer
- 4-5: Weak step-by-step reasoning, limited structure or explicit reasoning
- 2-3: Poor step-by-step reasoning, minimal structure, unclear progression
- 0-1: Very poor step-by-step reasoning, no clear structure, random or disconnected ideas

Return ONLY valid JSON with this structure:
{
    "score": <integer 0-10>,
    "explanation": "<brief explanation of step-by-step reasoning quality, highlighting strengths and weaknesses>"
}"""


def _get_openai_client() -> OpenAI | None:
    """Get OpenAI client using OPENAI_API_KEY from environment.
    
    Returns:
        OpenAI client if API key is available, None otherwise
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


async def _call_openai(prompt: str, system_prompt: str | None = None) -> str:
    """Call OpenAI API directly.
    
    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        
    Returns:
        Response text from OpenAI
        
    Raises:
        ValueError: If API key is not set or API call fails
    """
    client = _get_openai_client()
    if not client:
        raise ValueError("OPENAI_API_KEY is not set in environment variables")
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    try:
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                timeout=30,
            )
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise ValueError(f"OpenAI API call failed: {str(e)}")


class StepByStepReasoningScorer:
    """Calculates score for step-by-step reasoning quality using LLM analysis."""

    def __init__(self, ai_service: AIPlatformService | None = None):
        """Initialize step-by-step reasoning scorer.
        
        Args:
            ai_service: Optional AI service (will use OpenAI directly if not provided)
        """
        self.ai_service = ai_service

    async def calculate_score(self, response: str, judge_platform_id: str = "openai") -> int:
        """Calculate score for step-by-step reasoning quality (0-10).
        
        Uses LLM to analyze whether the response demonstrates clear, structured
        logical progression with explicit reasoning steps.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (default: "openai")
            
        Returns:
            Score between 0-10 where:
            - 10 = Excellent step-by-step reasoning with clear structure
            - 0 = Very poor step-by-step reasoning, no clear structure
        """
        # If response is too short, default score
        if len(response.strip()) < 50:
            return 6
        
        # Limit response length for LLM
        response_text = response[:10000] if len(response) > 10000 else response
        
        user_prompt = f"""Analyze the following response for step-by-step reasoning quality.

RESPONSE TO ANALYZE:
{response_text}

TASK:
Evaluate the step-by-step reasoning quality by assessing:
1. Whether the response shows clear, structured logical progression
2. Whether reasoning steps are explicitly stated
3. Whether there are proper transitions between ideas
4. Whether logical connectors are used appropriately
5. Whether the argument flows logically from premises to conclusions

Focus on the STRUCTURE and EXPLICITNESS of the reasoning, not on whether the conclusions are correct.

Return ONLY valid JSON with this structure:
{{
    "score": <integer 0-10>,
    "explanation": "<brief explanation of step-by-step reasoning quality, highlighting specific examples from the response>"
}}"""
        
        try:
            if self.ai_service:
                llm_response = await self.ai_service.get_response(
                    judge_platform_id,
                    user_prompt,
                    system_prompt=STEP_BY_STEP_REASONING_SYSTEM_PROMPT
                )
            else:
                llm_response = await _call_openai(
                    user_prompt,
                    system_prompt=STEP_BY_STEP_REASONING_SYSTEM_PROMPT
                )
            
            # Parse JSON response
            try:
                json_match = re.search(r'\{.*?"score".*?\}', llm_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    score = int(result.get("score", 6))
                else:
                    # Fallback: extract score using utility function
                    score = extract_json_score(llm_response, default_score=6)
            except (json.JSONDecodeError, ValueError, KeyError):
                # Fallback: extract score using utility function
                score = extract_json_score(llm_response, default_score=6)
            
            return clamp_score(score)
            
        except Exception as e:
            # Return default score on error
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "step_by_step_reasoning_calculation_failed",
                error=str(e),
                exc_info=True,
            )
            return 6

