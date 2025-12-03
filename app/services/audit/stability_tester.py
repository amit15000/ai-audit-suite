"""Service for testing stability and robustness of AI responses."""
from __future__ import annotations

from typing import Any

import structlog

from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class StabilityTester:
    """Tests stability by asking the same question multiple times."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def test_stability(
        self,
        prompt: str,
        platform_id: str,
        iterations: int = 10,
    ) -> dict[str, Any]:
        """Test stability by asking the same question multiple times.
        
        Args:
            prompt: The prompt to test
            platform_id: Platform to test
            iterations: Number of times to ask (default: 10)
            
        Returns:
            Dictionary with stability score, similarity metrics, and results
        """
        responses = []
        
        # Collect responses
        for i in range(iterations):
            try:
                response = await self.ai_service.get_response(
                    platform_id,
                    prompt,
                    system_prompt="You are a helpful AI assistant."
                )
                responses.append(response)
            except Exception as e:
                logger.warning("stability.response_collection_failed", iteration=i, error=str(e))
                continue
        
        if len(responses) < 2:
            return {
                "score": 5,
                "error": "Insufficient responses collected",
                "explanation": "Could not collect enough responses for stability testing."
            }
        
        # Calculate similarity between responses
        similarities = self._calculate_similarities(responses)
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
        
        # Calculate stability score (0-10)
        stability_score = int(avg_similarity * 10)
        
        # Check for drastic variations
        variations = self._detect_variations(responses)
        
        return {
            "score": stability_score,
            "iterations": len(responses),
            "average_similarity": avg_similarity,
            "similarities": similarities,
            "variations_detected": len(variations),
            "variations": variations,
            "explanation": self._generate_explanation(stability_score, avg_similarity, len(variations))
        }

    def _calculate_similarities(self, responses: list[str]) -> list[float]:
        """Calculate pairwise similarities between responses."""
        similarities = []
        
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                similarity = self._text_similarity(responses[i], responses[j])
                similarities.append(similarity)
        
        return similarities

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity (0-1)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

    def _detect_variations(self, responses: list[str]) -> list[dict[str, Any]]:
        """Detect drastic variations in responses."""
        variations = []
        
        if len(responses) < 2:
            return variations
        
        # Calculate average length
        avg_length = sum(len(r) for r in responses) / len(responses)
        
        for i, response in enumerate(responses):
            length_diff = abs(len(response) - avg_length) / avg_length if avg_length > 0 else 0
            
            # Flag if length differs by more than 50%
            if length_diff > 0.5:
                variations.append({
                    "iteration": i,
                    "type": "length_variation",
                    "description": f"Response length differs significantly from average ({length_diff:.1%} difference)"
                })
        
        return variations

    def _generate_explanation(
        self, score: int, avg_similarity: float, variation_count: int
    ) -> str:
        """Generate explanation for stability score."""
        if score >= 8:
            base = f"High stability: Responses are consistent (similarity: {avg_similarity:.2%})."
        elif score >= 6:
            base = f"Moderate stability: Responses show some variation (similarity: {avg_similarity:.2%})."
        else:
            base = f"Low stability: Responses vary significantly (similarity: {avg_similarity:.2%})."
        
        if variation_count > 0:
            base += f" {variation_count} drastic variation(s) detected."
        
        return base

