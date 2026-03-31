"""Multi-LLM comparison score calculation for hallucination detection."""
from __future__ import annotations

import asyncio
import json
import os
import re

import httpx
from openai import OpenAI

from app.services.comparison.hallucination.utils import (
    extract_json_score,
    clamp_score,
)


# System prompt for LLM judge to compare responses
MULTI_LLM_COMPARISON_SYSTEM_PROMPT = """You are an expert at detecting hallucinations by comparing LLM responses.

Your expertise lies in identifying when a TARGET response contains information that differs significantly from what OTHER LLM responses agree on.

CORE PRINCIPLE:
If multiple LLMs (trained on similar data) produce similar responses, and one response contains unique claims or contradicts the consensus, those differences are likely hallucinations.

YOUR TASK:
Compare the TARGET response against REFERENCE responses from other LLMs to identify:
1. UNIQUE CLAIMS: Facts/claims that appear ONLY in target (not in reference responses) → likely hallucination
2. CONTRADICTORY CLAIMS: Target says X, but reference responses say Y → likely hallucination
3. CONSENSUS CLAIMS: Claims that all/most responses agree on → likely accurate

FOCUS ON SEMANTIC MEANING:
- Understand the MEANING of statements, not just word matching
- "X is 100" and "X is 200" = CONTRADICTORY (same entity, incompatible values)
- "X is 100" and "Y is 200" = NOT CONTRADICTORY (different entities)
- "X increased" and "X decreased" = CONTRADICTORY (semantic opposites)
- "X increased" and "X went up" = NOT CONTRADICTORY (same meaning, different words)

SEVERITY LEVELS:
- HIGH: Major factual contradictions, critical unique claims that contradict consensus
- MEDIUM: Moderate differences, some unique claims that may be incorrect
- LOW: Minor differences, stylistic variations, or complementary information

OUTPUT REQUIREMENTS:
Return ONLY valid JSON with this exact structure:
{
    "score": <0-10 where 10=perfect consensus, 0=major outlier>,
    "consensus_alignment": <0-100 percentage of alignment with reference responses>,
    "unique_claims_count": <number of unique claims found>,
    "contradictory_claims_count": <number of contradictory claims found>,
    "consensus_claims_count": <number of claims where all agree>,
    "unique_claims": [
        {
            "claim": "<exact claim text from target response>",
            "explanation": "<why this is unique and potentially a hallucination>",
            "severity": "<low|medium|high>"
        }
    ],
    "contradictory_claims": [
        {
            "target_claim": "<exact claim from target>",
            "consensus_claim": "<what reference responses say>",
            "consensus_count": <number of reference responses agreeing>,
            "explanation": "<why this is contradictory>",
            "severity": "<low|medium|high>"
        }
    ],
    "consensus_claims": [
        {
            "claim": "<claim text>",
            "agreement_count": <number of responses agreeing>,
            "total_responses": <total number of reference responses>
        }
    ],
    "explanation": "<overall explanation of comparison results>"
}

SCORING GUIDELINES:
- 10: Perfect consensus, all claims align with reference responses
- 8-9: Minor unique claims, mostly aligned (1-2 low severity)
- 6-7: Some unique/contradictory claims, moderate divergence (2-3 medium severity)
- 4-5: Many unique claims, significant divergence (3-5 medium/high severity)
- 2-3: Major outlier, most claims differ (5+ high severity)
- 0-1: Completely different, no alignment (many severe contradictions)"""


def _get_openai_client() -> OpenAI | None:
    """Get OpenAI client instance.
    
    Returns:
        OpenAI client or None if API key not set
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
                timeout=60,  # Longer timeout for comparison
            )
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise ValueError(f"OpenAI API call failed: {str(e)}")


async def _call_gemini(prompt: str, system_prompt: str | None = None) -> str:
    """Call Gemini API directly.
    
    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        
    Returns:
        Response text from Gemini
        
    Raises:
        ValueError: If API key is not set or API call fails
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is not set in environment variables")
    
    model = "gemini-2.0-flash-exp"
    base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    request_body = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }
    
    if system_prompt:
        request_body["systemInstruction"] = {
            "parts": [{"text": system_prompt}]
        }
    
    url = f"{base_url}/models/{model}:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=request_body, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            candidates = data.get("candidates")
            if not candidates:
                error_msg = data.get("error", {}).get("message", "No candidates in response")
                raise ValueError(f"Gemini API error: {error_msg}")
            
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts") or []
            
            if not parts:
                raise ValueError("Gemini API: missing parts in content")
            
            text = parts[0].get("text", "")
            if not text:
                raise ValueError("Gemini API returned empty text")
            
            return text
    except Exception as e:
        raise ValueError(f"Gemini API call failed: {str(e)}")


async def _call_groq(prompt: str, system_prompt: str | None = None) -> str:
    """Call Groq API directly.
    
    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        
    Returns:
        Response text from Groq
        
    Raises:
        ValueError: If API key is not set or API call fails
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables")
    
    model = "llama-3.1-70b-versatile"
    base_url = "https://api.groq.com/openai/v1"
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    request_body = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=request_body, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("Groq API returned no choices")
            
            message = choices[0].get("message", {})
            text = message.get("content", "")
            
            if not text:
                raise ValueError("Groq API returned empty text")
            
            return text
    except Exception as e:
        raise ValueError(f"Groq API call failed: {str(e)}")


class MultiLLMComparisonScorer:
    """Detects hallucinations by generating responses from multiple LLMs and comparing target response."""

    # List of available LLM platforms (easily extensible for future additions)
    AVAILABLE_LLM_PLATFORMS = ["openai", "gemini", "groq"]
    
    def __init__(self, ai_service=None):
        """Initialize multi-LLM comparison scorer.
        
        Args:
            ai_service: Not used (kept for backward compatibility)
        """
        pass

    async def calculate_score(
        self,
        target_response: str,
        original_prompt: str,
        target_platform_id: str,
        judge_platform_id: str = "openai",
        use_llm: bool = True,
        all_responses: dict[str, str] | None = None,
    ) -> int:
        """Calculate score by comparing target response against other LLM responses (0-10).
        
        Uses existing responses from all_responses if available (when user selected multiple platforms),
        otherwise generates responses from remaining LLMs (excluding target platform), then compares
        target response against these reference responses to detect hallucinations.
        
        Args:
            target_response: The response text to evaluate
            original_prompt: The original prompt that generated target_response
            target_platform_id: Platform ID that generated target_response (to exclude from reference generation)
            judge_platform_id: Platform ID for LLM judge comparison
            use_llm: Whether to use LLM (must be True for this scorer to work)
            all_responses: Optional dictionary of all existing responses (if user already selected multiple platforms)
            
        Returns:
            Score between 0-10 where:
            - 10 = Perfect consensus with reference LLMs
            - 0 = Major outlier, completely different
            
        Raises:
            ValueError: If use_llm is False (LLM is required for this scorer)
        """
        if not use_llm:
            raise ValueError(
                "LLM is required for multi-LLM comparison. "
                "Set use_llm=True to enable comparison analysis."
            )
        
        # Get detailed comparison
        detailed_result = await self.get_detailed_comparison(
            target_response, original_prompt, target_platform_id, judge_platform_id, use_llm=True, all_responses=all_responses
        )
        
        return clamp_score(detailed_result["score"])
    
    async def get_detailed_comparison(
        self,
        target_response: str,
        original_prompt: str,
        target_platform_id: str,
        judge_platform_id: str = "openai",
        use_llm: bool = True,
        all_responses: dict[str, str] | None = None,
    ) -> dict:
        """Get detailed comparison results with unique claims, contradictions, and consensus.
        
        Args:
            target_response: The response text to evaluate
            original_prompt: The original prompt that generated target_response
            target_platform_id: Platform ID that generated target_response
            judge_platform_id: Platform ID for LLM judge comparison
            use_llm: Whether to use LLM (must be True)
            all_responses: Optional dictionary of all existing responses (if user already selected multiple platforms)
            
        Returns:
            Dictionary with:
            - score: int (0-10)
            - consensus_alignment: float (0-100)
            - unique_claims_count: int
            - contradictory_claims_count: int
            - consensus_claims_count: int
            - unique_claims: list of dicts
            - contradictory_claims: list of dicts
            - consensus_claims: list of dicts
            - reference_llms_used: list of platform IDs
            - explanation: str
            
        Raises:
            ValueError: If use_llm is False
        """
        if not use_llm:
            raise ValueError(
                "LLM is required for multi-LLM comparison. "
                "Set use_llm=True to enable comparison analysis."
            )
        
        # Step 1: Get reference responses (use existing if available, otherwise generate new)
        reference_responses = await self._get_reference_responses(
            original_prompt, target_platform_id, all_responses
        )
        
        if not reference_responses:
            # No reference responses available, return neutral score
            return {
                "score": 6,
                "consensus_alignment": 50.0,
                "unique_claims_count": 0,
                "contradictory_claims_count": 0,
                "consensus_claims_count": 0,
                "unique_claims": [],
                "contradictory_claims": [],
                "consensus_claims": [],
                "reference_llms_used": [],
                "explanation": "No reference LLM responses available for comparison. Need at least 2 LLMs (excluding target platform)."
            }
        
        # Step 2: Compare with LLM judge
        comparison_result = await self._compare_with_llm_judge(
            target_response, reference_responses, judge_platform_id
        )
        
        # Add reference LLMs used
        comparison_result["reference_llms_used"] = list(reference_responses.keys())
        
        return comparison_result
    
    async def _get_reference_responses(
        self,
        original_prompt: str,
        target_platform_id: str,
        all_responses: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Get reference responses from other LLMs.
        
        First tries to use existing responses from all_responses (if user already selected multiple platforms).
        If not enough responses available, generates new ones from remaining LLMs.
        
        Args:
            original_prompt: The original prompt
            target_platform_id: Platform ID to exclude
            all_responses: Optional dictionary of all existing responses
            
        Returns:
            Dictionary mapping platform_id to response text
        """
        reference_responses = {}
        
        # Step 1: Try to use existing responses from all_responses (if available)
        if all_responses:
            for platform_id, response_text in all_responses.items():
                # Exclude target platform and ensure response is valid
                if platform_id != target_platform_id and response_text and not response_text.startswith("Error:"):
                    reference_responses[platform_id] = response_text
        
        # Step 2: If we don't have enough reference responses, generate new ones
        # We want at least 2 reference responses for meaningful comparison
        if len(reference_responses) < 2:
            # Generate from remaining LLMs that we don't already have
            existing_platforms = set(reference_responses.keys()) | {target_platform_id}
            platforms_to_generate = [
                platform_id
                for platform_id in self.AVAILABLE_LLM_PLATFORMS
                if platform_id not in existing_platforms
            ]
            
            if platforms_to_generate:
                generated_responses = await self._generate_reference_responses(
                    original_prompt, target_platform_id, exclude_platforms=existing_platforms
                )
                reference_responses.update(generated_responses)
        
        return reference_responses
    
    async def _generate_reference_responses(
        self, prompt: str, exclude_platform_id: str, exclude_platforms: set[str] | None = None
    ) -> dict[str, str]:
        """Generate responses from multiple LLMs in parallel (excluding specified platforms).
        
        Args:
            prompt: The prompt to send to all LLMs
            exclude_platform_id: Platform ID to exclude (the target platform)
            exclude_platforms: Additional set of platform IDs to exclude (e.g., already have responses from these)
            
        Returns:
            Dictionary mapping platform_id to response text
        """
        # Build set of platforms to exclude
        exclude_set = {exclude_platform_id}
        if exclude_platforms:
            exclude_set.update(exclude_platforms)
        
        # Get list of platforms to use (exclude specified platforms)
        platforms_to_use = [
            platform_id
            for platform_id in self.AVAILABLE_LLM_PLATFORMS
            if platform_id not in exclude_set
        ]
        
        if not platforms_to_use:
            return {}
        
        # Generate responses in parallel
        async def generate_single_response(platform_id: str) -> tuple[str, str]:
            """Generate response from a single platform using direct API calls."""
            try:
                if platform_id == "openai":
                    response = await _call_openai(prompt)
                elif platform_id == "gemini":
                    response = await _call_gemini(prompt)
                elif platform_id == "groq":
                    response = await _call_groq(prompt)
                else:
                    raise ValueError(f"Unsupported platform: {platform_id}")
                return (platform_id, response)
            except Exception as e:
                # Log error but continue with other platforms
                import structlog
                logger = structlog.get_logger(__name__)
                logger.warning(
                    "multi_llm_comparison.reference_generation_failed",
                    platform_id=platform_id,
                    error=str(e),
                )
                return (platform_id, None)  # type: ignore
        
        # Generate all responses in parallel
        tasks = [generate_single_response(platform_id) for platform_id in platforms_to_use]
        results = await asyncio.gather(*tasks)
        
        # Filter out failed responses
        reference_responses = {
            platform_id: response
            for platform_id, response in results
            if response is not None
        }
        
        return reference_responses
    
    async def _compare_with_llm_judge(
        self,
        target_response: str,
        reference_responses: dict[str, str],
        judge_platform_id: str,
    ) -> dict:
        """Use LLM judge to compare target response against reference responses.
        
        Args:
            target_response: The target response to evaluate
            reference_responses: Dictionary of reference responses from other LLMs
            judge_platform_id: Platform ID for LLM judge
            
        Returns:
            Dictionary with comparison results
        """
        # Limit response lengths for LLM (keep it reasonable)
        target_text = target_response[:8000] if len(target_response) > 8000 else target_response
        
        # Format reference responses
        reference_texts = []
        for platform_id, response_text in reference_responses.items():
            limited_text = response_text[:8000] if len(response_text) > 8000 else response_text
            reference_texts.append(f"**{platform_id.upper()} Response:**\n{limited_text}")
        
        reference_section = "\n\n".join(reference_texts)
        
        user_prompt = f"""Compare the TARGET response against REFERENCE responses from other LLMs to detect hallucinations.

TARGET RESPONSE (to evaluate):
{target_text}

REFERENCE RESPONSES (from other LLMs):
{reference_section}

ANALYSIS TASK:
1. Identify UNIQUE CLAIMS: Facts/claims that appear ONLY in target (not in reference responses) → likely hallucination
2. Identify CONTRADICTORY CLAIMS: Target says X, but reference responses say Y → likely hallucination
3. Identify CONSENSUS CLAIMS: Claims that all/most responses agree on → likely accurate

Focus on SEMANTIC MEANING, not just word matching.

Return ONLY valid JSON with this structure:
{{
    "score": <0-10>,
    "consensus_alignment": <0-100>,
    "unique_claims_count": <number>,
    "contradictory_claims_count": <number>,
    "consensus_claims_count": <number>,
    "unique_claims": [...],
    "contradictory_claims": [...],
    "consensus_claims": [...],
    "explanation": "<overall explanation>"
}}"""
        
        # Use direct API calls based on judge platform
        if judge_platform_id == "openai":
            llm_response = await _call_openai(
                user_prompt,
                system_prompt=MULTI_LLM_COMPARISON_SYSTEM_PROMPT
            )
        elif judge_platform_id == "gemini":
            llm_response = await _call_gemini(
                user_prompt,
                system_prompt=MULTI_LLM_COMPARISON_SYSTEM_PROMPT
            )
        elif judge_platform_id == "groq":
            llm_response = await _call_groq(
                user_prompt,
                system_prompt=MULTI_LLM_COMPARISON_SYSTEM_PROMPT
            )
        else:
            # Default to OpenAI if platform not recognized
            llm_response = await _call_openai(
                user_prompt,
                system_prompt=MULTI_LLM_COMPARISON_SYSTEM_PROMPT
            )
        
        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)
            else:
                # Try parsing entire response
                result = json.loads(llm_response)
        except json.JSONDecodeError as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "multi_llm_comparison.json_parse_failed",
                error=str(e),
                response_preview=llm_response[:200],
            )
            # Return default result on parse failure
            return {
                "score": 6,
                "consensus_alignment": 50.0,
                "unique_claims_count": 0,
                "contradictory_claims_count": 0,
                "consensus_claims_count": 0,
                "unique_claims": [],
                "contradictory_claims": [],
                "consensus_claims": [],
                "explanation": f"Failed to parse LLM response: {str(e)}"
            }
        
        # Extract score and ensure all fields are present
        score = extract_json_score(llm_response, default_score=6)
        result["score"] = clamp_score(score)
        
        # Ensure all required fields exist
        result.setdefault("consensus_alignment", 50.0)
        result.setdefault("unique_claims_count", len(result.get("unique_claims", [])))
        result.setdefault("contradictory_claims_count", len(result.get("contradictory_claims", [])))
        result.setdefault("consensus_claims_count", len(result.get("consensus_claims", [])))
        result.setdefault("unique_claims", [])
        result.setdefault("contradictory_claims", [])
        result.setdefault("consensus_claims", [])
        result.setdefault("explanation", "Comparison completed")
        
        return result
