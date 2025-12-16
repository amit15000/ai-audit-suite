"""Base class for deviation map scorers with shared helper methods."""
from __future__ import annotations

import re
from typing import List


class DeviationMapBase:
    """Base class with shared helper methods for deviation map scorers."""

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

