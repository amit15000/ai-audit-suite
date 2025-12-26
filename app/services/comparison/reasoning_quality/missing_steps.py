"""Missing steps detection for reasoning quality scoring."""
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


MISSING_STEPS_SYSTEM_PROMPT = """You are an expert evaluator specializing in detecting gaps and missing steps in logical reasoning.

Your expertise lies in identifying:
- Gaps in logical progression where steps are skipped
- Jumps in reasoning without proper transitions
- Incomplete arguments where conclusions lack proper support
- Missing logical links between premises and conclusions

CORE PRINCIPLES:
1. **Complete Reasoning Chain**: Arguments should have all necessary steps explicitly stated
2. **Logical Gaps**: Identify when reasoning jumps from one point to another without connecting steps
3. **Supporting Evidence**: Conclusions should be properly supported by premises
4. **Missing Links**: Identify where additional reasoning steps are needed to make the argument complete

WHAT TO LOOK FOR:

NEGATIVE INDICATORS (Low Score - Missing Steps Present):
- Abrupt transitions from premise to conclusion without intermediate steps
- Claims made without supporting reasoning
- Logical jumps that leave gaps in the reasoning chain
- Conclusions that don't follow clearly from the premises
- Missing explanations for key transitions
- Unsupported assertions
- Gaps where additional reasoning is needed to connect ideas

POSITIVE INDICATORS (High Score - No Missing Steps):
- Complete reasoning chains from premises to conclusions
- All necessary steps explicitly stated
- Smooth transitions between ideas
- Each conclusion properly supported by preceding reasoning
- No logical gaps in the argument flow

SCORING GUIDELINES:
- 10: No missing steps detected, complete reasoning chain
- 8-9: Minor gaps, mostly complete reasoning
- 6-7: Some missing steps, but main reasoning is present
- 4-5: Significant gaps in reasoning, several missing steps
- 2-3: Major gaps, incomplete reasoning chains
- 0-1: Critical gaps, many missing steps, reasoning is incomplete

Return ONLY valid JSON with this structure:
{
    "score": <integer 0-10>,
    "explanation": "<brief explanation of missing steps detected, identifying specific gaps in the reasoning>"
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


class MissingStepsScorer:
    """Calculates score for detecting missing steps in reasoning using LLM analysis."""

    def __init__(self, ai_service: AIPlatformService | None = None):
        """Initialize missing steps scorer.
        
        Args:
            ai_service: Optional AI service (will use OpenAI directly if not provided)
        """
        self.ai_service = ai_service

    async def calculate_score(self, response: str, judge_platform_id: str = "openai") -> int:
        """Calculate score for missing steps detection (0-10).
        
        Uses LLM to identify gaps in logical progression and missing steps
        in the reasoning chain.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (default: "openai")
            
        Returns:
            Score between 0-10 where:
            - 10 = No missing steps detected, complete reasoning chain
            - 0 = Critical gaps, many missing steps, reasoning is incomplete
        """
        # If response is too short, default score
        if len(response.strip()) < 50:
            return 6
        
        # Limit response length for LLM
        response_text = response[:10000] if len(response) > 10000 else response
        
        user_prompt = f"""Analyze the following response for missing steps in logical reasoning.

RESPONSE TO ANALYZE:
{response_text}

TASK:
Identify gaps and missing steps in the logical reasoning by assessing:
1. Whether there are abrupt jumps from premises to conclusions
2. Whether all necessary reasoning steps are explicitly stated
3. Whether conclusions are properly supported by preceding reasoning
4. Whether there are logical gaps where additional steps are needed
5. Whether the reasoning chain is complete from start to finish

Focus on COMPLETENESS of the reasoning chain, not on whether the conclusions are correct.

Return ONLY valid JSON with this structure:
{{
    "score": <integer 0-10>,
    "explanation": "<brief explanation of missing steps detected, identifying specific gaps in the reasoning chain>"
}}"""
        
        try:
            if self.ai_service:
                llm_response = await self.ai_service.get_response(
                    judge_platform_id,
                    user_prompt,
                    system_prompt=MISSING_STEPS_SYSTEM_PROMPT
                )
            else:
                llm_response = await _call_openai(
                    user_prompt,
                    system_prompt=MISSING_STEPS_SYSTEM_PROMPT
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
                "missing_steps_calculation_failed",
                error=str(e),
                exc_info=True,
            )
            return 6

