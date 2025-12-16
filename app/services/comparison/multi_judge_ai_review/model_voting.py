"""Model voting score calculation for multi-judge AI review detection."""
from __future__ import annotations

from typing import Dict

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.multi_judge_ai_review.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    clamp_percentage,
)


class ModelVotingScorer:
    """Calculates model voting percentage."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize model voting scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, all_responses: Dict[str, str], judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate model voting percentage (0-100).
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Model voting percentage (0-100)
        """
        if len(all_responses) <= 1:
            return 100.0  # Only one model, assume 100% voting
        
        # Calculate consensus (voting agreement)
        response_words = set(response.lower().split())
        response_words = {w for w in response_words if len(w) > 2}
        
        agreements = 0
        for other_response in all_responses.values():
            if other_response == response:
                continue
            
            other_words = set(other_response.lower().split())
            other_words = {w for w in other_words if len(w) > 2}
            
            if response_words and other_words:
                intersection = len(response_words & other_words)
                union = len(response_words | other_words)
                similarity = intersection / union if union > 0 else 0
                if similarity > 0.7:  # High similarity = agreement
                    agreements += 1
        
        total_comparisons = len(all_responses) - 1
        if total_comparisons == 0:
            return 100.0
        
        base_percentage = (agreements / total_comparisons) * 100
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the model voting agreement percentage (0-100) across multiple models:

Response: {response[:1000]}
Other responses count: {len(all_responses) - 1}

Return ONLY JSON: {{"modelVoting": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_percentage = extract_json_float(judge_response, "modelVoting", base_percentage)
                base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return clamp_percentage(base_percentage)

