"""Contradictory information score calculation for hallucination detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.hallucination.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_score,
    clamp_score,
)
from app.services.comparison.hallucination.contradiction_helpers import (
    extract_factual_claims,
    detect_claim_contradictions,
    detect_semantic_contradictions,
    detect_explicit_contradictions,
    are_opposite_values,
)


class ContradictoryInfoScorer:
    """Calculates score for identifying contradictory information."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize contradictory info scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for identifying contradictory information (0-10).
        
        Uses semantic analysis and claim comparison to detect actual contradictions.
        Higher score = fewer contradictions detected.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced analysis (default: False)
            
        Returns:
            Score between 0-10
        """
        # Split into sentences for analysis
        sentences = re.split(r'[.!?]+', response)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        if len(sentences) < 2:
            return 9  # Single sentence or too short, no contradictions possible
        
        contradiction_score = 0.0  # Start with 0 contradictions detected
        
        # Method 1: Extract and compare factual claims (weight: 1.0)
        factual_claims = extract_factual_claims(sentences)
        claim_contradictions = detect_claim_contradictions(factual_claims)
        contradiction_score += claim_contradictions * 1.0  # Full weight for explicit contradictions
        
        # Method 2: Detect semantic contradictions using embeddings (weight: 0.7)
        # This is less reliable but catches subtle contradictions
        semantic_contradiction_score = 0.0
        try:
            from app.services.embedding.embedding_service import EmbeddingService
            from app.services.embedding.similarity_service import SimilarityService
            
            embedding_service = EmbeddingService()
            similarity_service = SimilarityService()
            
            # Generate embeddings for sentences (limit for performance)
            sentence_embeddings = []
            max_sentences = min(25, len(sentences))  # Increased limit for better coverage
            for sentence in sentences[:max_sentences]:
                if len(sentence.strip()) > 15:  # Only meaningful sentences
                    try:
                        embedding = await embedding_service.generate_embedding(sentence)
                        sentence_embeddings.append((sentence, embedding))
                    except Exception:
                        continue
            
            # Compare sentence pairs for semantic contradictions
            if len(sentence_embeddings) >= 2:
                semantic_contradiction_score = detect_semantic_contradictions(
                    sentence_embeddings, similarity_service
                )
                contradiction_score += semantic_contradiction_score * 0.7  # Reduced weight
        except Exception:
            # If embeddings fail, fall back to text-based analysis
            pass
        
        # Method 3: Detect explicit contradiction patterns (weight: 1.2)
        # Most reliable method - explicit contradictions are clear indicators
        explicit_contradictions = detect_explicit_contradictions(sentences)
        contradiction_score += explicit_contradictions * 1.2  # Higher weight for explicit
        
        # Method 4: Temporal/logical consistency check (weight: 0.8)
        temporal_contradictions = self._detect_temporal_contradictions(sentences)
        contradiction_score += temporal_contradictions * 0.8
        
        # Normalize by text length (longer texts may have more contradictions naturally)
        # But don't over-normalize - contradictions are still problematic
        text_length_factor = min(1.0, 500 / max(len(response), 100))
        contradiction_score = contradiction_score * (0.7 + 0.3 * text_length_factor)
        
        # Convert contradiction score to final score (0-10)
        # Higher contradiction_score = lower final score
        # Normalize: 0 contradictions = 10, many contradictions = 0
        final_score = self._contradiction_score_to_final_score(contradiction_score)
        
        # Optional LLM enhancement for validation
        if use_llm and contradiction_score > 0:
            final_score = await self._apply_llm_enhancement(
                response, final_score, judge_platform_id
            )
        
        return clamp_score(final_score)

    def _contradiction_score_to_final_score(self, contradiction_score: float) -> float:
        """Convert contradiction score to final score (0-10).
        
        Uses a more nuanced scoring system that considers:
        - Severity of contradictions (explicit vs implicit)
        - Frequency relative to text length
        - Impact on overall coherence
        
        Args:
            contradiction_score: Weighted number of contradictions detected
            
        Returns:
            Final score (0-10, where 10 = no contradictions)
        """
        # Normalize contradiction score (higher = more severe)
        if contradiction_score == 0:
            return 10.0  # Perfect: no contradictions
        elif contradiction_score < 0.5:
            return 9.5  # Excellent: minimal contradictions
        elif contradiction_score < 1.0:
            return 9.0  # Very good: very few contradictions
        elif contradiction_score < 1.5:
            return 8.0  # Good: few contradictions
        elif contradiction_score < 2.0:
            return 7.0  # Acceptable: some contradictions
        elif contradiction_score < 3.0:
            return 5.0  # Poor: moderate contradictions
        elif contradiction_score < 4.0:
            return 3.0  # Critical: significant contradictions
        elif contradiction_score < 6.0:
            return 1.5  # Severe: many contradictions
        else:
            return 0.5  # Critical: extensive contradictions

    def _detect_temporal_contradictions(self, sentences: list[str]) -> float:
        """Detect temporal and logical consistency issues.
        
        Looks for contradictions in:
        - Time sequences (e.g., "X happened in 2020" vs "X happened in 2021")
        - Cause-effect relationships
        - Conditional logic
        
        Args:
            sentences: List of sentences to analyze
            
        Returns:
            Contradiction score
        """
        contradiction_count = 0.0
        
        # Extract temporal claims
        temporal_pattern = r'\b(in|on|during|since|until|before|after)\s+(\d{4})\b'
        temporal_claims = []
        
        for idx, sentence in enumerate(sentences):
            matches = re.finditer(temporal_pattern, sentence, re.IGNORECASE)
            for match in matches:
                temporal_claims.append({
                    'sentence_idx': idx,
                    'sentence': sentence,
                    'temporal_marker': match.group(1).lower(),
                    'year': int(match.group(2))
                })
        
        # Check for conflicting temporal claims about same subject
        if len(temporal_claims) >= 2:
            for i, claim1 in enumerate(temporal_claims):
                for claim2 in temporal_claims[i+1:]:
                    # Check if same sentence or adjacent sentences with same subject
                    if abs(claim1['sentence_idx'] - claim2['sentence_idx']) <= 2:
                        # Check for conflicting years (same event, different year)
                        if abs(claim1['year'] - claim2['year']) > 0:
                            # Extract potential subject (words before temporal marker)
                            sent1_words = set(claim1['sentence'].lower().split()[:10])
                            sent2_words = set(claim2['sentence'].lower().split()[:10])
                            common_words = sent1_words & sent2_words
                            
                            # If they share significant words, might be same event
                            if len(common_words) >= 3:
                                contradiction_count += 0.5
        
        # Check for logical contradictions (if-then patterns)
        conditional_pattern = r'\b(if|when|whenever)\s+([^.!?]+?)\s+(?:then|,)\s+([^.!?]+?)(?:[.!?]|$)'
        conditionals = []
        for sentence in sentences:
            matches = re.finditer(conditional_pattern, sentence, re.IGNORECASE)
            for match in matches:
                conditionals.append({
                    'condition': match.group(2).lower(),
                    'consequence': match.group(3).lower()
                })
        
        # Check for contradictory conditionals
        for i, cond1 in enumerate(conditionals):
            for cond2 in conditionals[i+1:]:
                # Same condition, opposite consequence
                if cond1['condition'] == cond2['condition']:
                    if are_opposite_values(cond1['consequence'], cond2['consequence']):
                        contradiction_count += 0.5
        
        return contradiction_count

    async def _apply_llm_enhancement(
        self, response: str, final_score: float, judge_platform_id: str
    ) -> float:
        """Apply LLM enhancement to score calculation.
        
        Uses LLM to detect subtle contradictions and logical inconsistencies
        that rule-based methods might miss.
        
        Args:
            response: Response text
            final_score: Current final score
            judge_platform_id: Platform ID for LLM
            
        Returns:
            Enhanced score
        """
        try:
            prompt = f"""Analyze this text comprehensively for internal contradictions and logical inconsistencies.

Look for:
1. Conflicting factual claims about the same subject
2. Statements that directly contradict each other
3. Temporal inconsistencies (same event, different times)
4. Logical inconsistencies (if A then B, but also if A then not B)
5. Causal contradictions (X causes Y, but also X prevents Y)

Text: {response[:2500]}

Return ONLY JSON: {{
    "contradictions_found": <number of distinct contradictions>,
    "severity": <"low"|"medium"|"high">,
    "score": <0-10 where 10=no contradictions, 0=many severe contradictions>,
    "explanation": "<brief explanation of contradictions found>"
}}"""
            
            judge_response = await self.ai_service.get_response(
                judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
            )
            
            llm_score = extract_json_score(judge_response, int(final_score))
            
            # Blend scores: 65% rule-based (objective detection), 35% LLM (nuanced validation)
            # Rule-based methods are more reliable for explicit contradictions,
            # LLM helps with subtle logical inconsistencies
            return final_score * 0.65 + llm_score * 0.35
        except Exception:
            return final_score

