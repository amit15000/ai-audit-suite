"""Multi-LLM comparison score calculation for hallucination detection."""
from __future__ import annotations

from app.services.comparison.hallucination.utils import clamp_score


class MultiLLMComparisonScorer:
    """Calculates score by comparing response against multiple LLM responses."""

    async def calculate_score(
        self, response: str, all_responses: dict[str, str], use_embeddings: bool = False
    ) -> int:
        """Calculate score by comparing response against multiple LLM responses (0-10).
        
        Uses a multi-metric approach:
        1. Word-based similarity (Jaccard, fast)
        2. Semantic similarity (embeddings, more accurate)
        3. Consensus analysis (agreement patterns)
        
        Higher score = higher consensus with other LLMs (less hallucination).
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings for better comparison (default: False)
            
        Returns:
            Score between 0-10
        """
        if len(all_responses) <= 1:
            # Only one response available, can't compare
            return 6
        
        # Method 1: Word-based Jaccard similarity (fast, deterministic)
        word_similarities = self._calculate_word_similarities(response, all_responses)
        
        if not word_similarities:
            return 6
        
        # Calculate average word similarity
        avg_word_similarity = sum(word_similarities) / len(word_similarities)
        
        # Method 2: Semantic similarity using embeddings (more accurate)
        avg_semantic_similarity = avg_word_similarity  # Default fallback
        if use_embeddings:
            avg_semantic_similarity = await self._calculate_semantic_similarities(
                response, all_responses
            )
        
        # Method 3: Consensus analysis (check if response is an outlier)
        consensus_score = self._calculate_consensus_score(
            word_similarities, avg_word_similarity
        )
        
        # Combine metrics with weighted average
        # Semantic similarity is most important (50%), word similarity (30%), consensus (20%)
        if use_embeddings:
            combined_similarity = (
                avg_semantic_similarity * 0.5 +
                avg_word_similarity * 0.3 +
                consensus_score * 0.2
            )
        else:
            # Without embeddings, rely more on word similarity and consensus
            combined_similarity = (
                avg_word_similarity * 0.6 +
                consensus_score * 0.4
            )
        
        # Convert similarity (0-1) to score (0-10)
        # Use non-linear scaling: high similarity gets higher scores
        if combined_similarity >= 0.9:
            score = 9.5 + (combined_similarity - 0.9) * 5  # 9.5-10 range
        elif combined_similarity >= 0.7:
            score = 8.0 + (combined_similarity - 0.7) * 7.5  # 8.0-9.5 range
        elif combined_similarity >= 0.5:
            score = 6.0 + (combined_similarity - 0.5) * 10  # 6.0-8.0 range
        elif combined_similarity >= 0.3:
            score = 4.0 + (combined_similarity - 0.3) * 10  # 4.0-6.0 range
        else:
            score = combined_similarity * 13.33  # 0-4.0 range
        
        return clamp_score(int(score))

    def _calculate_word_similarities(
        self, response: str, all_responses: dict[str, str]
    ) -> list[float]:
        """Calculate word-based Jaccard similarities with improved tokenization.
        
        Uses better word filtering and normalization for more accurate comparison.
        
        Args:
            response: Response text to compare
            all_responses: Dictionary of all LLM responses
            
        Returns:
            List of similarity scores
        """
        similarities = []
        
        # Improved tokenization: remove punctuation, normalize
        import string
        response_words = self._extract_meaningful_words(response)
        
        for other_response in all_responses.values():
            if other_response == response:
                continue
            
            other_words = self._extract_meaningful_words(other_response)
            
            if response_words and other_words:
                # Jaccard similarity
                intersection = len(response_words & other_words)
                union = len(response_words | other_words)
                similarity = intersection / union if union > 0 else 0
                similarities.append(similarity)
        
        return similarities

    def _extract_meaningful_words(self, text: str) -> set[str]:
        """Extract meaningful words from text for comparison.
        
        Filters out:
        - Very short words (< 3 chars)
        - Common stop words
        - Punctuation-only tokens
        
        Args:
            text: Text to extract words from
            
        Returns:
            Set of normalized meaningful words
        """
        import string
        
        # Common stop words to filter
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this',
            'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their'
        }
        
        # Normalize and tokenize
        text_lower = text.lower()
        # Remove punctuation except apostrophes (for contractions)
        text_clean = ''.join(c if c.isalnum() or c.isspace() or c == "'" else ' ' for c in text_lower)
        words = text_clean.split()
        
        # Filter meaningful words
        meaningful = {
            w.strip("'") for w in words
            if len(w.strip("'")) >= 3 and w.strip("'") not in stop_words
        }
        
        return meaningful

    def _calculate_consensus_score(
        self, similarities: list[float], avg_similarity: float
    ) -> float:
        """Calculate consensus score based on similarity distribution.
        
        Measures how consistent the response is with the group.
        High variance = outlier = lower consensus.
        
        Args:
            similarities: List of similarity scores
            avg_similarity: Average similarity
            
        Returns:
            Consensus score (0-1)
        """
        if not similarities or len(similarities) < 2:
            return avg_similarity
        
        # Calculate variance (lower variance = higher consensus)
        variance = sum((s - avg_similarity) ** 2 for s in similarities) / len(similarities)
        
        # Normalize variance to 0-1 scale (assuming max variance ~0.25)
        normalized_variance = min(1.0, variance / 0.25)
        
        # Consensus score: high average + low variance = high consensus
        consensus = avg_similarity * (1.0 - normalized_variance * 0.3)
        
        return max(0.0, min(1.0, consensus))

    async def _calculate_semantic_similarities(
        self, response: str, all_responses: dict[str, str]
    ) -> float:
        """Calculate semantic similarities using embeddings.
        
        Args:
            response: Response text to compare
            all_responses: Dictionary of all LLM responses
            
        Returns:
            Average semantic similarity (0-1)
        """
        try:
            from app.services.embedding.embedding_service import EmbeddingService
            from app.services.embedding.similarity_service import SimilarityService
            
            embedding_service = EmbeddingService()
            similarity_service = SimilarityService()
            
            # Generate embedding for main response
            response_embedding = await embedding_service.generate_embedding(response)
            semantic_similarities = []
            
            for other_response in all_responses.values():
                if other_response == response:
                    continue
                
                other_embedding = await embedding_service.generate_embedding(other_response)
                semantic_sim = similarity_service.cosine_similarity(
                    response_embedding, other_embedding
                )
                semantic_similarities.append(max(0.0, semantic_sim))  # Ensure non-negative
            
            if semantic_similarities:
                return sum(semantic_similarities) / len(semantic_similarities)
        except Exception:
            pass  # Fall back to word-based similarity
        
        return 0.0


