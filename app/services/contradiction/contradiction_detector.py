"""Service for detecting contradictions between LLM responses using an evaluator LLM."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import structlog
from openai import OpenAI

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class ContradictionDetector:
    """Detects contradictions between multiple LLM responses using an evaluator LLM."""

    def __init__(self, evaluator_platform: str = "openai") -> None:
        """Initialize ContradictionDetector with evaluator LLM.
        
        Args:
            evaluator_platform: Platform ID to use as evaluator (default: "openai")
        """
        self.evaluator_platform = evaluator_platform
        settings = get_settings()
        
        # Get OpenAI API key for evaluator
        api_key = (
            settings.adapter.openai_api_key
            or os.getenv("OPENAI_API_KEY")
        )
        
        if api_key:
            self._client = OpenAI(api_key=api_key)
            self._use_openai = True
        else:
            self._client = None
            self._use_openai = False
            logger.warning(
                "OPENAI_API_KEY not found. ContradictionDetector will use placeholder detection. "
                "Set OPENAI_API_KEY in .env file or as ADAPTER_OPENAI_API_KEY to enable LLM-based contradiction detection."
            )

    def detect_contradictions(
        self, 
        responses: Dict[str, str],
        prompt: str | None = None
    ) -> List[Dict[str, Any]]:
        """Detect contradictions between multiple responses.
        
        Args:
            responses: Dictionary mapping provider_id to response text
            prompt: Optional original prompt that generated these responses
            
        Returns:
            List of contradiction dictionaries with structured information
        """
        if len(responses) < 2:
            logger.warning("contradiction.insufficient_responses", count=len(responses))
            return []
        
        logger.info(
            "contradiction.detection_start",
            response_count=len(responses),
            providers=list(responses.keys())
        )
        
        if self._use_openai and self._client:
            contradictions = self._detect_with_llm(responses, prompt)
        else:
            contradictions = self._placeholder_detection(responses)
        
        logger.info(
            "contradiction.detection_complete",
            contradiction_count=len(contradictions)
        )
        
        return contradictions

    def _detect_with_llm(
        self, 
        responses: Dict[str, str],
        prompt: str | None = None
    ) -> List[Dict[str, Any]]:
        """Use evaluator LLM to detect contradictions."""
        if not self._client:
            return self._placeholder_detection(responses)
        
        # Format responses for the evaluator
        responses_text = "\n\n".join(
            f"Response from {provider_id}:\n{response_text}"
            for provider_id, response_text in responses.items()
        )
        
        evaluation_prompt = f"""You are an expert evaluator tasked with identifying contradictions between multiple AI-generated responses.

Your task is to analyze the following responses and identify any conflicting statements, factual disagreements, logical inconsistencies, or contradictory claims.

{f"Original Prompt:\n{prompt}\n\n" if prompt else ""}Responses to analyze:
{responses_text}

Please identify all contradictions between these responses. For each contradiction, provide:
1. The exact conflicting statements from each response
2. The source/provider of each statement
3. The type of contradiction (factual, temporal, logical, numerical, definitional, etc.)
4. The severity level (low, medium, high, critical)
5. A clear explanation of why these statements contradict

Return your analysis as a JSON object with a "contradictions" key containing an array of contradiction objects. Each object should have this structure:
{{
    "statement_1": "<exact text from first response>",
    "statement_2": "<exact text from second response>",
    "source_1": "<provider_id>",
    "source_2": "<provider_id>",
    "contradiction_type": "<type>",
    "severity": "<low|medium|high|critical>",
    "explanation": "<detailed explanation>"
}}

Example format:
{{
    "contradictions": [
        {{
            "statement_1": "...",
            "statement_2": "...",
            "source_1": "openai",
            "source_2": "gemini",
            "contradiction_type": "factual",
            "severity": "high",
            "explanation": "..."
        }}
    ]
}}

If no contradictions are found, return: {{"contradictions": []}}

Return ONLY valid JSON, no other text."""

        try:
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert contradiction detection system. Your role is to:
1. Identify factual, logical, temporal, or definitional contradictions between responses
2. Extract exact conflicting statements with their sources
3. Classify the type and severity of each contradiction
4. Provide clear explanations

Be thorough but precise. Only flag genuine contradictions, not differences in style or emphasis.
Focus on substantive disagreements in facts, numbers, dates, definitions, or logical conclusions."""
                    },
                    {
                        "role": "user",
                        "content": evaluation_prompt
                    }
                ],
                temperature=0.2,  # Low temperature for consistency
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content or "{}"
            
            # Parse the response - should be a JSON object with "contradictions" key
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    # Extract contradictions array from the response
                    contradictions = parsed.get("contradictions", [])
                    if isinstance(contradictions, list):
                        return contradictions
                    return []
                elif isinstance(parsed, list):
                    # Fallback: if it's a direct array, use it
                    return parsed
                else:
                    return []
            except json.JSONDecodeError as e:
                logger.error("contradiction.json_parse_error", error=str(e), content=content[:200])
                return self._placeholder_detection(responses)
                
        except Exception as e:
            logger.error("contradiction.llm_error", error=str(e), exc_info=True)
            # Fallback to placeholder detection
            return self._placeholder_detection(responses)

    def _placeholder_detection(
        self, 
        responses: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Placeholder contradiction detection for testing without LLM."""
        logger.debug("contradiction.using_placeholder")
        
        # Simple heuristic: if responses are very different in length or content, flag as potential contradiction
        contradictions: List[Dict[str, Any]] = []
        response_list = list(responses.items())
        
        for i in range(len(response_list)):
            for j in range(i + 1, len(response_list)):
                provider_1, text_1 = response_list[i]
                provider_2, text_2 = response_list[j]
                
                # Simple heuristic: if length difference is >50%, consider it a potential contradiction
                len_diff_ratio = abs(len(text_1) - len(text_2)) / max(len(text_1), len(text_2), 1)
                
                if len_diff_ratio > 0.5:
                    contradictions.append({
                        "statement_1": text_1[:100] + "..." if len(text_1) > 100 else text_1,
                        "statement_2": text_2[:100] + "..." if len(text_2) > 100 else text_2,
                        "source_1": provider_1,
                        "source_2": provider_2,
                        "contradiction_type": "length_discrepancy",
                        "severity": "medium",
                        "explanation": f"Significant length difference ({len_diff_ratio:.1%}) suggests potential content disagreement. Enable LLM evaluator for detailed analysis."
                    })
        
        return contradictions

