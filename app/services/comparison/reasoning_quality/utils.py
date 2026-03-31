"""Shared utilities for reasoning quality scoring modules."""
from __future__ import annotations

import json
import re

from app.services.comparison.hallucination.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_score,
    clamp_score,
)

__all__ = [
    "JUDGE_SYSTEM_PROMPT",
    "extract_json_score",
    "clamp_score",
    "extract_score_and_explanation",
]


def extract_score_and_explanation(response: str, default_score: int = 6) -> tuple[int, str]:
    """Extract score and explanation from LLM JSON response.
    
    Args:
        response: LLM response text
        default_score: Default score if extraction fails
        
    Returns:
        Tuple of (score: int, explanation: str)
    """
    if not response or not response.strip():
        return default_score, "No response received"
    
    # Strategy 1: Try parsing entire response as JSON
    try:
        data = json.loads(response.strip())
        score = int(data.get("score", default_score))
        explanation = str(data.get("explanation", "")).strip()
        return clamp_score(score), explanation if explanation else "No explanation provided"
    except (json.JSONDecodeError, ValueError, KeyError):
        pass
    
    # Strategy 2: Look for JSON code blocks (```json ... ```)
    code_block_match = re.search(
        r'```(?:json)?\s*(\{.*?\})\s*```',
        response,
        re.DOTALL | re.IGNORECASE,
    )
    if code_block_match:
        try:
            data = json.loads(code_block_match.group(1))
            score = int(data.get("score", default_score))
            explanation = str(data.get("explanation", "")).strip()
            return clamp_score(score), explanation if explanation else "No explanation provided"
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    
    # Strategy 3: Extract JSON object using flexible regex
    json_match = re.search(r'\{.*?"score".*?"explanation".*?\}', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            score = int(data.get("score", default_score))
            explanation = str(data.get("explanation", "")).strip()
            return clamp_score(score), explanation if explanation else "No explanation provided"
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    
    # Strategy 4: Extract score separately, then try to find explanation
    score = extract_json_score(response, default_score=default_score)
    explanation_match = re.search(r'"explanation"\s*:\s*"([^"]*)"', response, re.IGNORECASE)
    explanation = explanation_match.group(1) if explanation_match else "Explanation not found in response"
    
    return clamp_score(score), explanation
