"""Service for testing prompt sensitivity."""
from __future__ import annotations

from typing import Any

import structlog

from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class SensitivityTester:
    """Tests how AI responses change with small prompt variations."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def test_sensitivity(
        self,
        original_prompt: str,
        platform_id: str,
        variations: list[str] | None = None,
    ) -> dict[str, Any]:
        """Test prompt sensitivity.
        
        Args:
            original_prompt: Original prompt
            platform_id: Platform to test
            variations: Optional custom variations (defaults to auto-generated)
            
        Returns:
            Dictionary with sensitivity score and variation analysis
        """
        if variations is None:
            variations = self._generate_variations(original_prompt)
        
        # Get original response
        try:
            original_response = await self.ai_service.get_response(
                platform_id,
                original_prompt,
                system_prompt="You are a helpful AI assistant."
            )
        except Exception as e:
            logger.warning("sensitivity.original_response_failed", error=str(e))
            return {
                "score": 5,
                "error": "Failed to get original response",
                "explanation": "Could not test sensitivity due to error."
            }
        
        # Get responses for variations
        variation_results = []
        for variation in variations:
            try:
                variation_response = await self.ai_service.get_response(
                    platform_id,
                    variation,
                    system_prompt="You are a helpful AI assistant."
                )
                
                similarity = self._text_similarity(original_response, variation_response)
                variation_results.append({
                    "variation": variation,
                    "response": variation_response[:200],
                    "similarity": similarity,
                    "significant_change": similarity < 0.7
                })
            except Exception as e:
                logger.warning("sensitivity.variation_response_failed", variation=variation, error=str(e))
                continue
        
        if not variation_results:
            return {
                "score": 5,
                "error": "No variation responses collected",
                "explanation": "Could not collect responses for variations."
            }
        
        # Calculate average similarity
        avg_similarity = sum(r["similarity"] for r in variation_results) / len(variation_results)
        
        # Count significant changes
        significant_changes = sum(1 for r in variation_results if r["significant_change"])
        
        # Calculate sensitivity score (higher similarity = lower sensitivity = higher score)
        sensitivity_score = int(avg_similarity * 10)
        
        return {
            "score": sensitivity_score,
            "original_prompt": original_prompt,
            "variations_tested": len(variation_results),
            "average_similarity": avg_similarity,
            "significant_changes": significant_changes,
            "variation_results": variation_results,
            "explanation": self._generate_explanation(sensitivity_score, avg_similarity, significant_changes)
        }

    def _generate_variations(self, prompt: str) -> list[str]:
        """Generate prompt variations (typos, paraphrases, etc.)."""
        variations = []
        
        # Add typo variations
        if len(prompt) > 10:
            # Simple typo: remove a letter
            typo1 = prompt.replace("the", "te", 1) if "the" in prompt else prompt[:-1] + prompt[-1].lower()
            variations.append(typo1)
            
            # Another typo: swap letters
            if len(prompt) > 5:
                words = prompt.split()
                if words:
                    # Add a typo to first word
                    first_word = words[0]
                    if len(first_word) > 2:
                        typo2 = first_word[:-1] + first_word[-1].upper() + " " + " ".join(words[1:])
                        variations.append(typo2)
        
        # Add paraphrase (simple - in production, use LLM for better paraphrasing)
        if "?" in prompt:
            variations.append(prompt.replace("?", "").strip() + "?")
        
        # Add spacing variation
        variations.append(prompt.replace("  ", " ").strip())
        
        return variations[:5]  # Limit to 5 variations

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity (0-1)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

    def _generate_explanation(
        self, score: int, avg_similarity: float, significant_changes: int
    ) -> str:
        """Generate explanation for sensitivity score."""
        if score >= 8:
            base = f"Low sensitivity: Responses remain consistent despite prompt variations (similarity: {avg_similarity:.2%})."
        elif score >= 6:
            base = f"Moderate sensitivity: Responses show some variation (similarity: {avg_similarity:.2%})."
        else:
            base = f"High sensitivity: Responses change significantly with prompt variations (similarity: {avg_similarity:.2%})."
        
        if significant_changes > 0:
            base += f" {significant_changes} significant change(s) detected."
        
        return base

