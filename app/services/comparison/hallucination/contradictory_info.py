"""Contradictory information score calculation for hallucination detection."""
from __future__ import annotations

import asyncio
import json
import os
import re

from openai import OpenAI

from app.services.comparison.hallucination.utils import (
    extract_json_score,
    clamp_score,
)


# High-quality system prompt for semantic contradiction detection
CONTRADICTION_DETECTION_SYSTEM_PROMPT = """You are an expert semantic analyst specializing in detecting contradictions in text.

Your expertise lies in understanding the MEANING and SEMANTIC CONTENT of statements, not just their surface-level words.

CORE PRINCIPLE:
A contradiction exists when two statements have SEMANTIC MEANINGS that cannot both be true simultaneously, even if they use different words or phrasing.

CONTRADICTION TYPES TO DETECT (with semantic understanding):

1. DIRECT SEMANTIC CONTRADICTIONS:
   - "X is true" vs "X is false" (same meaning, opposite truth values)
   - "X exists" vs "X does not exist" (semantic opposites)
   - "X is present" vs "X is absent" (mutually exclusive states)

2. FACTUAL SEMANTIC CONTRADICTIONS:
   - Same entity/subject with conflicting factual attributes
   - "The population is 8 million" vs "The population is 10 million" (same subject, incompatible values)
   - "The event occurred in 2020" vs "The event occurred in 2021" (same event, incompatible times)
   - "The value increased" vs "The value decreased" (same metric, opposite directions)

3. TEMPORAL SEMANTIC CONTRADICTIONS:
   - Same event with incompatible temporal attributes
   - "X happened before Y" vs "X happened after Y" (same events, opposite order)
   - "X was completed in 2020" vs "X was completed in 2021" (same completion, different times)

4. LOGICAL SEMANTIC CONTRADICTIONS:
   - Same condition leading to incompatible consequences
   - "If A then B" vs "If A then not B" (same condition, opposite outcomes)
   - "When X occurs, Y happens" vs "When X occurs, Y does not happen"

5. CAUSAL SEMANTIC CONTRADICTIONS:
   - Same cause with incompatible effects
   - "X causes Y" vs "X prevents Y" (same cause, opposite effects)
   - "X leads to Y" vs "X leads to not Y"

6. ATTRIBUTIVE SEMANTIC CONTRADICTIONS:
   - Same entity with incompatible attributes
   - "X is beneficial" vs "X is harmful" (same entity, opposite evaluations)
   - "X is large" vs "X is small" (same entity, incompatible sizes)

SEMANTIC ANALYSIS REQUIREMENTS:

1. UNDERSTAND MEANING, NOT JUST WORDS:
   - "The city has 8 million people" and "The population is 8 million" = SAME MEANING (not contradictory)
   - "The city has 8 million people" and "The city has 10 million people" = CONTRADICTORY (same subject, different values)
   - "The study shows positive results" and "The research indicates benefits" = SAME MEANING (not contradictory)
   - "The study shows positive results" and "The study shows negative results" = CONTRADICTORY

2. IDENTIFY SEMANTIC EQUIVALENCE:
   - Recognize when different phrasings express the same meaning
   - "X increased" = "X went up" = "X grew" (semantically equivalent)
   - "X decreased" = "X went down" = "X reduced" (semantically equivalent)
   - "X increased" vs "X decreased" = CONTRADICTORY

3. DETECT SEMANTIC OPPOSITES:
   - Understand when concepts are semantically opposite
   - true/false, present/absent, increase/decrease, before/after, cause/prevent
   - "X is true" and "X is false" = CONTRADICTORY (semantic opposites)

4. CONTEXT-AWARE SEMANTIC ANALYSIS:
   - Consider the semantic context of statements
   - "The temperature is high" and "The temperature is low" = CONTRADICTORY (if same time/place)
   - "The temperature is high in summer" and "The temperature is low in winter" = NOT CONTRADICTORY (different contexts)

5. ENTITY RESOLUTION:
   - Identify when different references point to the same semantic entity
   - "New York City" = "NYC" = "The Big Apple" (same entity)
   - "The study" and "This research" (if referring to same study) = same entity

CRITICAL RULES:

✅ DO FLAG:
- Statements with same semantic subject but incompatible attributes
- Statements that are semantically opposite
- Statements that cannot both be true in the same context
- Factual contradictions (same fact, different values)
- Logical contradictions (same premise, opposite conclusions)

❌ DO NOT FLAG:
- Different perspectives on the same topic (opinions can coexist)
- Complementary information (different aspects of same topic)
- Different examples illustrating the same point
- Statements about different entities (even if similar)
- Statements in different contexts (different times, places, conditions)
- Stylistic variations expressing the same meaning

OUTPUT REQUIREMENTS:
Return ONLY valid JSON with this exact structure:
{
    "contradictions_found": <integer: number of distinct contradictions>,
    "contradiction_pairs": [
        {
            "statement_1": "<exact text from response showing first contradictory statement>",
            "statement_2": "<exact text from response showing second contradictory statement>",
            "type": "<direct|factual|temporal|logical|causal|attributive>",
            "severity": "<low|medium|high>",
            "semantic_reasoning": "<brief explanation of why these are semantically contradictory>"
        }
    ],
    "score": <integer 0-10 where 10=no contradictions, 0=many severe contradictions>,
    "explanation": "<brief explanation of contradictions found, focusing on semantic meaning>"
}

SCORING GUIDELINES:
- 10: No contradictions found (all statements are semantically consistent)
- 8-9: Minor contradictions (1-2 low severity)
- 6-7: Moderate contradictions (2-3 medium severity)
- 4-5: Significant contradictions (3-5 medium/high severity)
- 2-3: Severe contradictions (5+ high severity)
- 0-1: Critical contradictions (many severe contradictions throughout)"""


def _calculate_contradiction_score_from_instances(contradiction_pairs: list, contradictions_found: int) -> float:
    """Calculate contradiction score (0-10) mathematically based on contradiction instances.
    
    Score calculation formula:
    - Base score starts at 10 (no contradictions)
    - Deduct points based on number and severity of contradictions
    - Higher severity and more contradictions = lower score
    
    Args:
        contradiction_pairs: List of contradiction pair dicts with 'severity' field (low/medium/high)
        contradictions_found: Total number of contradictions found (may differ from len(pairs) if counting is different)
        
    Returns:
        Contradiction score (0-10) where 10 = no contradictions, 0 = many severe contradictions
    """
    if not contradiction_pairs and contradictions_found == 0:
        return 10.0
    
    # Use contradictions_found if pairs list is empty but count is provided
    if not contradiction_pairs and contradictions_found > 0:
        # Estimate severity distribution if we only have count
        # Assume medium severity for unclassified contradictions
        high_severity_count = 0
        medium_severity_count = contradictions_found
        low_severity_count = 0
    else:
        # Count instances by severity from pairs
        high_severity_count = sum(1 for c in contradiction_pairs if c.get("severity", "medium").lower() == "high")
        medium_severity_count = sum(1 for c in contradiction_pairs if c.get("severity", "medium").lower() == "medium")
        low_severity_count = sum(1 for c in contradiction_pairs if c.get("severity", "medium").lower() == "low")
        # If contradictions_found > len(pairs), add remaining as medium severity
        remaining = contradictions_found - len(contradiction_pairs)
        if remaining > 0:
            medium_severity_count += remaining
    
    total_count = contradictions_found if contradictions_found > 0 else len(contradiction_pairs)
    
    # Calculate penalty points based on severity-weighted formula
    # High severity: 4.0 points each (very severe - contradictions are serious issues)
    # Medium severity: 2.5 points each (moderate - multiple contradictions are problematic)
    # Low severity: 1.5 points each (minor but still indicates issues)
    
    penalty_points = (high_severity_count * 4.0) + (medium_severity_count * 2.5) + (low_severity_count * 1.5)
    
    # Apply extra penalty for high severity instances (contradictions are very serious issues)
    if high_severity_count > 0:
        penalty_points += high_severity_count * 0.5
    
    # Additional penalty for having multiple contradictions (cumulative effect)
    if total_count >= 2:
        penalty_points += (total_count - 1) * 0.5  # Extra 0.5 per contradiction beyond 1
    
    # Calculate score: start from 10, subtract penalties
    score = 10.0 - penalty_points
    
    # Ensure score is within bounds (0-10)
    return max(0.0, min(10.0, score))


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


class ContradictoryInfoScorer:
    """Calculates score for identifying contradictory information using LLM semantic analysis."""

    def __init__(self, ai_service=None):
        """Initialize contradictory info scorer.
        
        Args:
            ai_service: Not used (kept for backward compatibility)
        """
        pass

    async def calculate_score(
        self, response: str, judge_platform_id: str = "openai", use_llm: bool = False
    ) -> int:
        """Calculate score for identifying contradictory information (0-10).
        
        Uses LLM with semantic analysis to detect statements that contradict each other.
        Higher score = fewer contradictions detected.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM (must be True for this scorer to work)
            
        Returns:
            Score between 0-10 where:
            - 10 = No contradictions found
            - 0 = Many severe contradictions found
            
        Raises:
            ValueError: If use_llm is False (LLM is required for this scorer)
        """
        # If response is too short, no contradictions possible
        if len(response.strip()) < 50:
            return 9
        
        # LLM is required for this scorer
        if not use_llm:
            raise ValueError(
                "LLM is required for contradictory information detection. "
                "Set use_llm=True to enable semantic contradiction analysis."
            )
        
        # Use LLM to detect contradictions
        score = await self._detect_contradictions_with_llm(
            response, judge_platform_id
        )
        return clamp_score(score)
    
    async def get_detailed_contradictions(
        self, response: str, judge_platform_id: str = "openai", use_llm: bool = False
    ) -> dict:
        """Get detailed contradiction analysis with pairs and explanations.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM (must be True)
            
        Returns:
            Dictionary with:
            - score: int (0-10)
            - contradictions_found: int
            - contradiction_pairs: list of dicts with statement_1, statement_2, type, severity, semantic_reasoning
            - explanation: str
            
        Raises:
            ValueError: If use_llm is False
        """
        # If response is too short, no contradictions possible
        if len(response.strip()) < 50:
            return {
                "score": 9,
                "contradictions_found": 0,
                "contradiction_pairs": [],
                "explanation": "Response too short for contradiction analysis"
            }
        
        # LLM is required
        if not use_llm:
            raise ValueError(
                "LLM is required for contradictory information detection. "
                "Set use_llm=True to enable semantic contradiction analysis."
            )
        
        # Get detailed analysis
        return await self._get_detailed_contradictions_with_llm(
            response, judge_platform_id
        )

    async def _detect_contradictions_with_llm(
        self, response: str, judge_platform_id: str
    ) -> float:
        """Detect contradictions using LLM with semantic analysis.
        
        This method uses advanced semantic understanding to identify contradictions
        by analyzing the MEANING of statements, not just their surface-level words.
        
        Args:
            response: Response text to analyze
            judge_platform_id: Platform ID for LLM
            
        Returns:
            Score (0-10) where 10 = no contradictions
        """
        # Limit response length for LLM (keep it reasonable, but allow longer texts)
        response_text = response[:10000] if len(response) > 10000 else response
        
        user_prompt = f"""Analyze the following text for internal contradictions using SEMANTIC MEANING analysis.

Your task is to identify when statements in the text have SEMANTIC MEANINGS that contradict each other.

KEY INSTRUCTIONS:
1. Focus on SEMANTIC MEANING, not just word matching
2. Identify when two statements cannot both be true simultaneously
3. Consider the context and entity resolution
4. Look for semantic opposites and incompatible attributes
5. Understand that different phrasings can express the same meaning

TEXT TO ANALYZE:
{response_text}

ANALYSIS PROCESS:
1. Identify all factual claims and statements
2. Group statements by semantic subject/entity
3. Compare statements about the same semantic entity
4. Detect when attributes, values, or properties are incompatible
5. Flag contradictions based on semantic meaning, not surface words

Remember:
- "X is 100" and "X is 200" = CONTRADICTORY (same entity, incompatible values)
- "X is 100" and "Y is 200" = NOT CONTRADICTORY (different entities)
- "X increased" and "X decreased" = CONTRADICTORY (semantic opposites)
- "X increased" and "X went up" = NOT CONTRADICTORY (same meaning, different words)

Return ONLY valid JSON with this structure:
{{
    "contradictions_found": <number of distinct contradictions>,
    "contradiction_pairs": [
        {{
            "statement_1": "<exact text from response>",
            "statement_2": "<exact text from response>",
            "type": "<direct|factual|temporal|logical|causal|attributive>",
            "severity": "<low|medium|high>",
            "semantic_reasoning": "<why these are semantically contradictory>"
        }}
    ],
    "score": <0-10 where 10=no contradictions, 0=many severe contradictions>,
    "explanation": "<brief explanation focusing on semantic contradictions found>"
}}"""
        
        llm_response = await _call_openai(
            user_prompt,
            system_prompt=CONTRADICTION_DETECTION_SYSTEM_PROMPT
        )
        
        # Parse JSON to get contradiction pairs for mathematical calculation
        try:
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                contradiction_pairs = result.get("contradiction_pairs", [])
                contradictions_found = result.get("contradictions_found", len(contradiction_pairs))
                # Calculate score mathematically
                score = _calculate_contradiction_score_from_instances(contradiction_pairs, contradictions_found)
            else:
                # Fallback: extract score directly
                score = extract_json_score(llm_response, default_score=6)
        except (json.JSONDecodeError, KeyError):
            # Fallback: extract score directly
            score = extract_json_score(llm_response, default_score=6)
        
        return clamp_score(score)
    
    async def _get_detailed_contradictions_with_llm(
        self, response: str, judge_platform_id: str
    ) -> dict:
        """Get detailed contradiction analysis with pairs and explanations.
        
        Args:
            response: Response text to analyze
            judge_platform_id: Platform ID for LLM
            
        Returns:
            Dictionary with detailed contradiction analysis
        """
        # Limit response length for LLM
        response_text = response[:10000] if len(response) > 10000 else response
        
        user_prompt = f"""Analyze the following text for internal contradictions using SEMANTIC MEANING analysis.

Your task is to identify when statements in the text have SEMANTIC MEANINGS that contradict each other.

KEY INSTRUCTIONS:
1. Focus on SEMANTIC MEANING, not just word matching
2. Identify when two statements cannot both be true simultaneously
3. Consider the context and entity resolution
4. Look for semantic opposites and incompatible attributes
5. Understand that different phrasings can express the same meaning

TEXT TO ANALYZE:
{response_text}

ANALYSIS PROCESS:
1. Identify all factual claims and statements
2. Group statements by semantic subject/entity
3. Compare statements about the same semantic entity
4. Detect when attributes, values, or properties are incompatible
5. Flag contradictions based on semantic meaning, not surface words

Remember:
- "X is 100" and "X is 200" = CONTRADICTORY (same entity, incompatible values)
- "X is 100" and "Y is 200" = NOT CONTRADICTORY (different entities)
- "X increased" and "X decreased" = CONTRADICTORY (semantic opposites)
- "X increased" and "X went up" = NOT CONTRADICTORY (same meaning, different words)

Return ONLY valid JSON with this structure:
{{
    "contradictions_found": <number of distinct contradictions>,
    "contradiction_pairs": [
        {{
            "statement_1": "<exact text from response>",
            "statement_2": "<exact text from response>",
            "type": "<direct|factual|temporal|logical|causal|attributive>",
            "severity": "<low|medium|high>",
            "semantic_reasoning": "<why these are semantically contradictory>"
        }}
    ],
    "score": <0-10 where 10=no contradictions, 0=many severe contradictions>,
    "explanation": "<brief explanation focusing on semantic contradictions found>"
}}"""
        
        llm_response = await _call_openai(
            user_prompt,
            system_prompt=CONTRADICTION_DETECTION_SYSTEM_PROMPT
        )
        
        # Parse JSON response
        try:
            # Extract JSON from response (handle cases where LLM adds extra text)
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                # Fallback: try to parse entire response
                result = json.loads(llm_response)
            
            # Ensure all required fields exist
            contradictions_found = result.get("contradictions_found", 0)
            contradiction_pairs = result.get("contradiction_pairs", [])
            explanation = result.get("explanation", "No explanation provided")
            
            # Calculate score mathematically based on detected contradictions
            # This ensures accurate scoring regardless of LLM interpretation
            calculated_score = _calculate_contradiction_score_from_instances(contradiction_pairs, contradictions_found)
            
            return {
                "score": clamp_score(calculated_score),
                "contradictions_found": contradictions_found,
                "contradiction_pairs": contradiction_pairs,
                "explanation": explanation
            }
        except (json.JSONDecodeError, KeyError) as e:
            # If parsing fails, return default structure
            return {
                "score": 6,
                "contradictions_found": 0,
                "contradiction_pairs": [],
                "explanation": f"Failed to parse LLM response: {str(e)}"
            }
