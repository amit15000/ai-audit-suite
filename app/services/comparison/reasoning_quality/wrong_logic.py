"""Wrong logic and fallacy detection for reasoning quality scoring."""
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


WRONG_LOGIC_SYSTEM_PROMPT = """You are an expert evaluator specializing in detecting logical fallacies and invalid reasoning patterns.

Your expertise lies in identifying:
- Common logical fallacies (ad hominem, false cause, circular reasoning, strawman, etc.)
- Invalid argument structures
- Non-sequiturs and illogical conclusions
- Logical inconsistencies in reasoning patterns

CORE PRINCIPLES:
1. **Valid Reasoning**: Arguments should follow logical rules and valid inference patterns
2. **Fallacy Detection**: Identify when reasoning violates logical principles
3. **Argument Structure**: Evaluate whether the argument structure is sound
4. **Logical Consistency**: Check for logical inconsistencies within the reasoning

COMMON LOGICAL FALLACIES TO DETECT:

1. **Ad Hominem**: Attacking the person instead of the argument
2. **False Cause (Post Hoc)**: Assuming correlation implies causation
3. **Circular Reasoning (Begging the Question)**: Using the conclusion as evidence
4. **Strawman**: Misrepresenting an opponent's argument to make it easier to attack
5. **False Dilemma**: Presenting only two options when more exist
6. **Slippery Slope**: Arguing that one thing will lead to extreme consequences
7. **Hasty Generalization**: Drawing conclusions from insufficient evidence
8. **Appeal to Authority**: Using an authority as evidence when they're not relevant
9. **Appeal to Emotion**: Using emotions instead of logic to support an argument
10. **Non Sequitur**: Conclusion doesn't follow from the premises
11. **Red Herring**: Introducing irrelevant information to distract
12. **Equivocation**: Using ambiguous language to make an argument seem valid

WHAT TO LOOK FOR:

NEGATIVE INDICATORS (Low Score - Wrong Logic Present):
- Logical fallacies in the reasoning
- Invalid argument structures
- Conclusions that don't follow logically from premises
- Circular reasoning patterns
- False causal relationships
- Generalizations from insufficient evidence

POSITIVE INDICATORS (High Score - Sound Logic):
- Valid logical reasoning patterns
- Sound argument structures
- Conclusions that follow logically from premises
- No logical fallacies detected
- Consistent logical principles applied

SCORING GUIDELINES:
- 10: No wrong logic detected, sound reasoning throughout
- 8-9: Minor logical issues, mostly sound reasoning
- 6-7: Some logical fallacies or invalid structures present
- 4-5: Several logical fallacies, significant reasoning errors
- 2-3: Many logical fallacies, poor reasoning quality
- 0-1: Critical logical errors, extensive fallacious reasoning

Return ONLY valid JSON with this structure:
{
    "score": <integer 0-10>,
    "explanation": "<brief explanation of wrong logic detected, identifying specific fallacies or invalid reasoning patterns>"
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


class WrongLogicScorer:
    """Calculates score for detecting wrong logic and fallacies using LLM analysis."""

    def __init__(self, ai_service: AIPlatformService | None = None):
        """Initialize wrong logic scorer.
        
        Args:
            ai_service: Optional AI service (will use OpenAI directly if not provided)
        """
        self.ai_service = ai_service

    async def calculate_score(self, response: str, judge_platform_id: str = "openai") -> int:
        """Calculate score for wrong logic detection (0-10).
        
        Uses LLM to identify logical fallacies and invalid reasoning patterns.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (default: "openai")
            
        Returns:
            Score between 0-10 where:
            - 10 = No wrong logic detected, sound reasoning throughout
            - 0 = Critical logical errors, extensive fallacious reasoning
        """
        # If response is too short, default score
        if len(response.strip()) < 50:
            return 6
        
        # Limit response length for LLM
        response_text = response[:10000] if len(response) > 10000 else response
        
        user_prompt = f"""Analyze the following response for logical fallacies and invalid reasoning patterns.

RESPONSE TO ANALYZE:
{response_text}

TASK:
Identify wrong logic and logical fallacies by assessing:
1. Whether there are common logical fallacies (ad hominem, false cause, circular reasoning, strawman, etc.)
2. Whether argument structures are valid
3. Whether conclusions follow logically from premises
4. Whether there are non-sequiturs or illogical jumps
5. Whether logical principles are consistently applied

Focus on LOGICAL VALIDITY of the reasoning, not on whether the conclusions are correct.

Return ONLY valid JSON with this structure:
{{
    "score": <integer 0-10>,
    "explanation": "<brief explanation of wrong logic detected, identifying specific fallacies or invalid reasoning patterns>"
}}"""
        
        try:
            if self.ai_service:
                llm_response = await self.ai_service.get_response(
                    judge_platform_id,
                    user_prompt,
                    system_prompt=WRONG_LOGIC_SYSTEM_PROMPT
                )
            else:
                llm_response = await _call_openai(
                    user_prompt,
                    system_prompt=WRONG_LOGIC_SYSTEM_PROMPT
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
                "wrong_logic_calculation_failed",
                error=str(e),
                exc_info=True,
            )
            return 6

