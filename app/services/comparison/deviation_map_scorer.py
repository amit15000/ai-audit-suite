"""Service for calculating deviation map scores and sub-scores."""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from app.domain.schemas import DeviationMapSubScore
from app.services.embedding.embedding_service import EmbeddingService
from app.services.embedding.similarity_service import SimilarityService


class DeviationMapScorer:
    """Service for calculating deviation map scores and sub-scores."""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.similarity_service = SimilarityService()

    async def calculate_sub_scores(
        self,
        response: str,
        all_responses: Dict[str, str],
        use_embeddings: bool = True,
    ) -> DeviationMapSubScore:
        """Calculate the 3 deviation map sub-scores.
        
        Uses sentence-level comparison to identify deviations and conflicts.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings (default: True)
        
        Returns:
            DeviationMapSubScore with:
            - sentenceLevelComparison: Percentage of sentence-level comparison (0-100)
            - highlightedDifferences: Percentage of highlighted differences (0-100)
            - colorCodedConflictAreas: Percentage of color-coded conflict areas (0-100)
        """
        if len(all_responses) < 2:
            return DeviationMapSubScore(
                sentenceLevelComparison=0.0,
                highlightedDifferences=0.0,
                colorCodedConflictAreas=0.0
            )
        
        # Calculate deviation metrics
        sentence_level = await self.calculate_sentence_level_comparison(
            response, all_responses, use_embeddings=use_embeddings
        )
        highlighted_differences = await self.calculate_highlighted_differences(
            response, all_responses, use_embeddings=use_embeddings
        )
        color_coded_conflicts = await self.calculate_color_coded_conflict_areas(
            response, all_responses, use_embeddings=use_embeddings
        )
        
        return DeviationMapSubScore(
            sentenceLevelComparison=sentence_level,
            highlightedDifferences=highlighted_differences,
            colorCodedConflictAreas=color_coded_conflicts,
        )

    async def calculate_sentence_level_comparison(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of sentence-level comparison (0-100).
        
        Measures how many sentences are compared across responses.
        Higher percentage = more comprehensive sentence-level analysis.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
        """
        # Split response into sentences
        response_sentences = self._split_into_sentences(response)
        
        if len(response_sentences) == 0:
            return 0.0
        
        # Compare each sentence with other responses
        compared_count = 0
        
        for sentence in response_sentences:
            if len(sentence.strip()) < 10:  # Skip very short sentences
                continue
            
            # Check if this sentence has matches in other responses
            has_match = False
            for other_response in all_responses.values():
                if other_response == response:
                    continue
                
                other_sentences = self._split_into_sentences(other_response)
                for other_sentence in other_sentences:
                    if use_embeddings:
                        try:
                            # Use semantic similarity
                            sent_emb = await self.embedding_service.generate_embedding(sentence)
                            other_emb = await self.embedding_service.generate_embedding(other_sentence)
                            similarity = self.similarity_service.cosine_similarity(sent_emb, other_emb)
                            if similarity > 0.5:  # Similar enough to be compared
                                has_match = True
                                break
                        except Exception:
                            # Fall back to word-based
                            if self._sentences_similar_word_based(sentence, other_sentence):
                                has_match = True
                                break
                    else:
                        if self._sentences_similar_word_based(sentence, other_sentence):
                            has_match = True
                            break
                
                if has_match:
                    break
                
                if has_match:
                    break
            
            if has_match:
                compared_count += 1
        
        # Calculate percentage
        if len(response_sentences) > 0:
            percentage = (compared_count / len(response_sentences)) * 100
            return min(100.0, percentage)
        return 0.0

    async def calculate_highlighted_differences(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of highlighted differences (0-100).
        
        Measures how many differences are identified and highlighted.
        Higher percentage = more differences detected.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
        """
        # Split into sentences
        response_sentences = self._split_into_sentences(response)
        
        if len(response_sentences) == 0:
            return 0.0
        
        differences_count = 0
        total_comparisons = 0
        
        for sentence in response_sentences:
            if len(sentence.strip()) < 10:
                continue
            
            for other_response in all_responses.values():
                if other_response == response:
                    continue
                
                total_comparisons += 1
                other_sentences = self._split_into_sentences(other_response)
                
                # Find most similar sentence
                max_similarity = 0.0
                for other_sentence in other_sentences:
                    if use_embeddings:
                        try:
                            sent_emb = await self.embedding_service.generate_embedding(sentence)
                            other_emb = await self.embedding_service.generate_embedding(other_sentence)
                            similarity = self.similarity_service.cosine_similarity(sent_emb, other_emb)
                            max_similarity = max(max_similarity, similarity)
                        except Exception:
                            similarity = self._sentence_similarity_word_based(sentence, other_sentence)
                            max_similarity = max(max_similarity, similarity)
                    else:
                        similarity = self._sentence_similarity_word_based(sentence, other_sentence)
                        max_similarity = max(max_similarity, similarity)
                
                # If similarity is low, it's a difference
                if max_similarity < 0.6:  # Threshold for difference
                    differences_count += 1
        
        # Calculate percentage
        if total_comparisons > 0:
            percentage = (differences_count / total_comparisons) * 100
            return min(100.0, percentage)
        return 0.0

    async def calculate_color_coded_conflict_areas(
        self, response: str, all_responses: Dict[str, str], use_embeddings: bool = True
    ) -> float:
        """Calculate percentage of color-coded conflict areas (0-100).
        
        Measures how many areas have conflicts that need color-coding.
        Higher percentage = more conflict areas detected.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings
        """
        # Split into sentences
        response_sentences = self._split_into_sentences(response)
        
        if len(response_sentences) == 0:
            return 0.0
        
        conflict_areas = 0
        
        # Check for contradictory information
        for i, sentence in enumerate(response_sentences):
            if len(sentence.strip()) < 10:
                continue
            
            # Check against other responses for contradictions
            for other_response in all_responses.values():
                if other_response == response:
                    continue
                
                other_sentences = self._split_into_sentences(other_response)
                
                # Look for contradictory sentences
                for other_sentence in other_sentences:
                    # Note: _are_contradictory is synchronous, no await needed
                    if self._are_contradictory(sentence, other_sentence, use_embeddings):
                        conflict_areas += 1
                        break
        
        # Calculate percentage based on number of sentences
        if len(response_sentences) > 0:
            percentage = (conflict_areas / len(response_sentences)) * 100
            return min(100.0, percentage)
        return 0.0

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

    def _sentences_similar_word_based(self, sent1: str, sent2: str) -> bool:
        """Check if two sentences are similar using word-based comparison."""
        words1 = set(sent1.lower().split())
        words2 = set(sent2.lower().split())
        
        if not words1 or not words2:
            return False
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        similarity = intersection / union if union > 0 else 0
        
        return similarity > 0.5

    def _sentence_similarity_word_based(self, sent1: str, sent2: str) -> float:
        """Calculate similarity between two sentences using word-based comparison."""
        words1 = set(sent1.lower().split())
        words2 = set(sent2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _are_contradictory(
        self, sent1: str, sent2: str, use_embeddings: bool = True
    ) -> bool:
        """Check if two sentences are contradictory."""
        # Check for explicit contradiction markers
        contradiction_markers = [
            'but', 'however', 'although', 'despite', 'whereas',
            'on the other hand', 'conversely', 'in contrast', 'opposite'
        ]
        
        sent1_lower = sent1.lower()
        sent2_lower = sent2.lower()
        
        # Check for negation patterns
        if ('not' in sent1_lower and sent2_lower.replace('not ', '').replace('not', '').strip() in sent1_lower) or \
           ('not' in sent2_lower and sent1_lower.replace('not ', '').replace('not', '').strip() in sent2_lower):
            return True
        
        # Check for opposite values
        opposites = [
            ('true', 'false'), ('yes', 'no'), ('correct', 'incorrect'),
            ('right', 'wrong'), ('exists', 'not exist'), ('present', 'absent'),
            ('positive', 'negative'), ('increase', 'decrease'), ('up', 'down'),
            ('more', 'less'), ('greater', 'smaller'), ('high', 'low')
        ]
        
        for opp1, opp2 in opposites:
            if (opp1 in sent1_lower and opp2 in sent2_lower) or \
               (opp2 in sent1_lower and opp1 in sent2_lower):
                return True
        
        # Check for contradiction markers
        for marker in contradiction_markers:
            if marker in sent1_lower or marker in sent2_lower:
                # Check if they share subjects (likely contradiction)
                words1 = set(sent1_lower.split())
                words2 = set(sent2_lower.split())
                if len(words1 & words2) >= 2:
                    return True
        
        return False

