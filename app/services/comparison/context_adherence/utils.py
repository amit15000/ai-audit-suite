"""Shared utilities for context adherence scoring."""
from __future__ import annotations

import json
import re

from app.services.comparison.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    extract_json_string,
    clamp_percentage,
)


def extract_json_explanation(response: str, default_explanation: str = "No explanation provided") -> str:
    """Extract explanation from LLM JSON response.
    
    Args:
        response: LLM response text
        default_explanation: Default explanation if extraction fails
        
    Returns:
        Extracted explanation string
    """
    if not response or not response.strip():
        return default_explanation
    
    # Try to extract JSON from response
    json_match = re.search(r'\{.*?"explanation"\s*:\s*"[^"]*".*?\}', response, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group(0))
            explanation = str(result.get("explanation", default_explanation)).strip()
            return explanation if explanation else default_explanation
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    
    # Try parsing entire response as JSON
    try:
        data = json.loads(response.strip())
        explanation = str(data.get("explanation", default_explanation)).strip()
        return explanation if explanation else default_explanation
    except (json.JSONDecodeError, ValueError, KeyError):
        pass
    
    # Try to find explanation in code blocks
    code_block_match = re.search(
        r'```(?:json)?\s*(\{.*?"explanation"[^}]*\})\s*```',
        response,
        re.DOTALL | re.IGNORECASE,
    )
    if code_block_match:
        try:
            data = json.loads(code_block_match.group(1))
            explanation = str(data.get("explanation", default_explanation)).strip()
            return explanation if explanation else default_explanation
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    
    return default_explanation


__all__ = [
    "JUDGE_SYSTEM_PROMPT",
    "extract_json_float",
    "extract_json_string",
    "extract_json_explanation",
    "clamp_percentage",
]

