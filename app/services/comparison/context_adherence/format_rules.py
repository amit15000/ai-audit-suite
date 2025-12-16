"""Format rules score calculation for context adherence detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.context_adherence.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class FormatRulesScorer:
    """Calculates format rules adherence percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize format rules scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, prompt: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate format rules adherence percentage (0-100).
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Format rules adherence percentage (0-100)
        """
        # Check for common format requirements
        format_indicators = {
            'bullet_points': r'^[\s]*[-*•]\s+',
            'numbered_list': r'^\d+[\.\)]\s+',
            'paragraphs': r'\n\n',
            'headings': r'^#+\s+',
            'code_blocks': r'```',
        }
        
        format_score = 0.0
        total_checks = 0
        
        # Check if response has structure
        has_structure = bool(re.search(r'\n\n', response)) or bool(re.search(r'^[\s]*[-*•]', response, re.MULTILINE))
        if has_structure:
            format_score += 20
        total_checks += 1
        
        # Check for proper punctuation
        has_punctuation = bool(re.search(r'[.!?]$', response.strip()))
        if has_punctuation:
            format_score += 20
        total_checks += 1
        
        # Check for capitalization
        has_capitalization = bool(re.search(r'^[A-Z]', response.strip()))
        if has_capitalization:
            format_score += 20
        total_checks += 1
        
        # Check for consistent formatting
        has_consistent_format = len(set(re.findall(r'\n', response))) <= 2
        if has_consistent_format:
            format_score += 20
        total_checks += 1
        
        # Check for no excessive whitespace
        no_excessive_whitespace = not bool(re.search(r'\s{3,}', response))
        if no_excessive_whitespace:
            format_score += 20
        total_checks += 1
        
        base_percentage = format_score
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt_text = f"""Calculate format rules adherence percentage (0-100) of this response:

Prompt: {prompt[:500] if prompt else 'No specific format requirements'}
Response: {response[:2000]}

Return ONLY JSON: {{"formatAdherence": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt_text, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "formatAdherence", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

