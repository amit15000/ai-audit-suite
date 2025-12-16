"""Fact checking score calculation for hallucination detection."""
from __future__ import annotations

import re

from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.hallucination.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_score,
    clamp_score,
)


class FactCheckingScorer:
    """Calculates fact-checking score against external sources.
    
    Uses a multi-layered approach:
    1. Citation verification (URL accessibility)
    2. Claim-source alignment (verify claims match cited sources)
    3. Claim specificity analysis (specific claims need citations)
    4. LLM enhancement for complex validation
    """

    def __init__(self, citation_verifier: CitationVerifier, ai_service: AIPlatformService):
        """Initialize fact checking scorer.
        
        Args:
            citation_verifier: Service for verifying citations
            ai_service: Service for LLM interactions
        """
        self.citation_verifier = citation_verifier
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for fact-checking against external sources (0-10).
        
        Uses comprehensive verification including citation accessibility,
        claim-source alignment, and claim specificity analysis.
        Higher score = better fact-checking (fewer hallucinations detected).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Score between 0-10
        """
        # Extract and verify citations
        verification_results = await self.citation_verifier.verify_all_citations(response)
        citation_stats = self.citation_verifier.get_citation_statistics(verification_results)
        
        # Step 1: Base score from citation verification
        base_score = self._calculate_base_score(citation_stats)
        
        # Step 2: Analyze claim specificity and verify claims against source content
        claim_analysis = await self._analyze_claims_and_citations(
            response, verification_results, use_llm=use_llm, judge_platform_id=judge_platform_id
        )
        
        # Step 3: Apply content-based adjustments (including claim verification)
        base_score = self._apply_content_adjustments(
            response, citation_stats, claim_analysis, base_score
        )
        
        # Step 4: Optional LLM enhancement for complex validation
        if use_llm and (self._count_factual_indicators(response) > 2 or citation_stats['total'] > 0):
            base_score = await self._apply_llm_enhancement(
                response, citation_stats, claim_analysis, base_score, judge_platform_id
            )
        
        return clamp_score(base_score)

    def _calculate_base_score(self, citation_stats: dict) -> float:
        """Calculate base score from citation statistics.
        
        Uses a more nuanced scoring system that considers both
        accessibility rate and the absolute number of valid citations.
        
        Args:
            citation_stats: Statistics from citation verification
            
        Returns:
            Base score (0-10)
        """
        if citation_stats['total'] == 0:
            # No citations found - neutral score (can't verify without citations)
            return 6.0
        
        accessibility_rate = citation_stats['accessibility_rate']
        accessible_count = citation_stats['accessible']
        total_count = citation_stats['total']
        
        # Weighted scoring: considers both rate and absolute numbers
        # High accessibility rate with multiple citations = highest score
        if accessibility_rate >= 0.9:
            if accessible_count >= 3:
                return 9.5  # Excellent: many accessible citations
            elif accessible_count >= 2:
                return 9.0  # Very good: multiple accessible citations
            else:
                return 8.5  # Good: single accessible citation
        elif accessibility_rate >= 0.7:
            if accessible_count >= 2:
                return 8.0  # Good: most citations accessible
            else:
                return 7.0  # Acceptable: some citations accessible
        elif accessibility_rate >= 0.5:
            return 6.0  # Neutral: half accessible
        elif accessibility_rate >= 0.3:
            return 4.0  # Poor: few accessible
        else:
            # Very low accessibility rate
            if total_count >= 3:
                return 2.0  # Critical: many citations but most invalid
            else:
                return 3.0  # Poor: few citations and most invalid

    async def _analyze_claims_and_citations(
        self, response: str, verification_results: list, use_llm: bool = False, judge_platform_id: str = None
    ) -> dict:
        """Analyze factual claims and verify them against citation sources.
        
        This method:
        1. Extracts specific factual claims
        2. Finds nearby citations for each claim
        3. Verifies if claims match the content on cited pages
        
        Args:
            response: Response text
            verification_results: Citation verification results
            use_llm: Whether to use LLM for semantic verification
            judge_platform_id: Platform ID for LLM (if use_llm=True)
            
        Returns:
            Dictionary with claim analysis metrics including verification results
        """
        # Extract specific factual claims (numbers, dates, statistics, named entities)
        specific_claims = self._extract_specific_claims(response)
        
        # Count claims that should have citations
        claims_needing_citations = sum(
            1 for claim in specific_claims if claim['needs_citation']
        )
        
        # Verify claims against source content
        verified_claims = 0
        verification_results_list = []
        citations_with_claims = 0
        
        for result in verification_results:
            if not result.is_accessible or not result.full_content:
                continue
            
            # Find claims near this citation (within 200 chars)
            citation_pos = result.citation.position
            nearby_claims = [
                c for c in specific_claims
                if abs(c['position'] - citation_pos) < 200
            ]
            
            if nearby_claims:
                citations_with_claims += 1
                
                # Verify each nearby claim against the source content
                for claim in nearby_claims:
                    verification = await self.citation_verifier.verify_claim_source_alignment(
                        claim['text'],
                        result,
                        use_llm=use_llm,
                        ai_service=self.ai_service if use_llm else None,
                        judge_platform_id=judge_platform_id if use_llm else None
                    )
                    
                    verification_results_list.append({
                        'claim': claim,
                        'verification': verification,
                        'citation': result.citation.url
                    })
                    
                    # Count verified claims (confidence >= 0.6)
                    if verification['verified'] and verification['confidence'] >= 0.6:
                        verified_claims += 1
        
        # Calculate verification rate
        total_verifiable_claims = len(verification_results_list)
        verification_rate = (
            verified_claims / total_verifiable_claims
            if total_verifiable_claims > 0 else 0.0
        )
        
        return {
            'total_specific_claims': len(specific_claims),
            'claims_needing_citations': claims_needing_citations,
            'citations_with_claims': citations_with_claims,
            'citation_coverage': (
                citations_with_claims / max(1, claims_needing_citations)
                if claims_needing_citations > 0 else 1.0
            ),
            'verified_claims': verified_claims,
            'total_verifiable_claims': total_verifiable_claims,
            'verification_rate': verification_rate,
            'verification_results': verification_results_list
        }

    def _extract_specific_claims(self, response: str) -> list[dict]:
        """Extract specific factual claims from response.
        
        Args:
            response: Response text
            
        Returns:
            List of claim dictionaries with position and metadata
        """
        claims = []
        
        # Pattern 1: Statistical claims (percentages, numbers with context)
        stat_pattern = r'(\d+\.?\d*%?)\s+(?:of|in|are|is|was|were|have|has)\s+([^.!?]{10,100}?)(?:[.!?]|$)'
        for match in re.finditer(stat_pattern, response, re.IGNORECASE):
            claims.append({
                'type': 'statistical',
                'text': match.group(0),
                'position': match.start(),
                'needs_citation': True  # Statistics always need citations
            })
        
        # Pattern 2: Date-based claims
        date_pattern = r'\b(?:in|on|during|since|until)\s+(\d{4})\b[^.!?]{10,100}?[.!?]'
        for match in re.finditer(date_pattern, response, re.IGNORECASE):
            claims.append({
                'type': 'temporal',
                'text': match.group(0),
                'position': match.start(),
                'needs_citation': True  # Historical claims need citations
            })
        
        # Pattern 3: Research/study claims
        research_pattern = r'(?:research|study|studies|survey|analysis|report)\s+(?:shows?|indicates?|finds?|suggests?|demonstrates?)[^.!?]{10,150}?[.!?]'
        for match in re.finditer(research_pattern, response, re.IGNORECASE):
            claims.append({
                'type': 'research',
                'text': match.group(0),
                'position': match.start(),
                'needs_citation': True  # Research claims must be cited
            })
        
        # Pattern 4: Named entity claims (organizations, people, places with factual statements)
        entity_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:is|are|was|were|has|have|reported|announced|stated)[^.!?]{10,100}?[.!?]'
        for match in re.finditer(entity_pattern, response):
            # Filter out common words that aren't entities
            entity = match.group(1)
            if len(entity.split()) <= 3 and entity not in ['The', 'This', 'That', 'These', 'Those']:
                claims.append({
                    'type': 'entity',
                    'text': match.group(0),
                    'position': match.start(),
                    'needs_citation': True  # Entity claims often need citations
                })
        
        return claims

    def _apply_content_adjustments(
        self, response: str, citation_stats: dict, claim_analysis: dict, base_score: float
    ) -> float:
        """Apply adjustments based on comprehensive content analysis.
        
        Args:
            response: Response text
            citation_stats: Citation statistics
            claim_analysis: Claim analysis results
            base_score: Current base score
            
        Returns:
            Adjusted score
        """
        score = base_score
        
        # Adjustment 1: Citation quality bonus/penalty
        if citation_stats['total'] > 0:
            # Bonus for multiple accessible citations
            if citation_stats['accessible'] >= 3:
                score += 0.5
            elif citation_stats['accessible'] >= 2:
                score += 0.3
            
            # Penalty for invalid citations (indicates potential fabrication)
            invalid_rate = citation_stats['invalid'] / citation_stats['total']
            if invalid_rate > 0.3:
                score -= min(2.0, invalid_rate * 5.0)  # Strong penalty for many invalid
        
        # Adjustment 2: Claim-citation alignment and verification
        if claim_analysis['claims_needing_citations'] > 0:
            coverage = claim_analysis['citation_coverage']
            if coverage >= 0.8:
                score += 0.5  # Bonus: most claims have nearby citations
            elif coverage >= 0.5:
                score += 0.2  # Small bonus: some alignment
            elif coverage < 0.3:
                score -= 1.0  # Penalty: claims without citations
        
        # Adjustment 2b: Claim-source verification (NEW - actual content verification)
        if claim_analysis['total_verifiable_claims'] > 0:
            verification_rate = claim_analysis['verification_rate']
            if verification_rate >= 0.8:
                score += 1.0  # Strong bonus: most claims verified in sources
            elif verification_rate >= 0.6:
                score += 0.5  # Bonus: majority of claims verified
            elif verification_rate >= 0.4:
                score += 0.2  # Small bonus: some claims verified
            elif verification_rate < 0.3:
                score -= 1.5  # Strong penalty: claims don't match sources (hallucination)
            elif verification_rate < 0.5:
                score -= 0.5  # Penalty: low verification rate
        
        # Adjustment 3: Vague vs specific claims
        vague_indicators = ["many", "some", "often", "usually", "generally", "typically", "commonly"]
        vague_count = sum(1 for indicator in vague_indicators if indicator in response.lower())
        specific_claims_count = claim_analysis['total_specific_claims']
        
        # If many vague claims but few specific ones, and no citations, penalty
        if vague_count > 3 and specific_claims_count < 2 and citation_stats['total'] == 0:
            score -= 0.5
        
        # Adjustment 4: Unverifiable claim patterns (red flags)
        unverifiable_patterns = [
            "experts say", "many believe", "it is said", "rumors suggest",
            "some claim", "allegedly", "supposedly", "reportedly"
        ]
        unverifiable_count = sum(
            1 for pattern in unverifiable_patterns if pattern in response.lower()
        )
        if unverifiable_count > 0:
            if citation_stats['total'] == 0:
                score -= min(2.0, unverifiable_count * 0.7)  # Strong penalty: unverifiable without citations
            elif unverifiable_count > 2:
                score -= 0.5  # Small penalty: too many unverifiable patterns
        
        # Adjustment 5: Factual indicator bonus (shows awareness of need for sources)
        factual_indicators = self._count_factual_indicators(response)
        if factual_indicators >= 3 and citation_stats['accessible'] >= 2:
            score += 0.3  # Bonus: uses factual language with citations
        
        return score

    def _count_factual_indicators(self, response: str) -> int:
        """Count factual indicator phrases in response.
        
        Args:
            response: Response text
            
        Returns:
            Count of factual indicators
        """
        factual_indicators = [
            "according to", "research shows", "studies indicate", "data suggests",
            "evidence indicates", "findings show", "statistics show", "reports indicate",
            "as stated in", "as reported by", "cited in", "referenced in"
        ]
        return sum(1 for indicator in factual_indicators if indicator in response.lower())

    async def _apply_llm_enhancement(
        self,
        response: str,
        citation_stats: dict,
        claim_analysis: dict,
        base_score: float,
        judge_platform_id: str
    ) -> float:
        """Apply LLM enhancement to score calculation.
        
        Uses LLM to validate claim-source alignment and detect subtle hallucinations.
        
        Args:
            response: Response text
            citation_stats: Citation statistics
            claim_analysis: Claim analysis results
            base_score: Current base score
            judge_platform_id: Platform ID for LLM
            
        Returns:
            Enhanced score
        """
        try:
            # Build comprehensive prompt with all analysis data
            citation_summary = (
                f"Found {citation_stats['total']} citations, "
                f"{citation_stats['accessible']} accessible, "
                f"{citation_stats['invalid']} invalid. "
                f"Accessibility rate: {citation_stats['accessibility_rate']:.1%}"
            )
            
            claim_summary = (
                f"Found {claim_analysis['total_specific_claims']} specific factual claims, "
                f"{claim_analysis['claims_needing_citations']} requiring citations, "
                f"citation coverage: {claim_analysis['citation_coverage']:.1%}"
            )
            
            prompt = f"""Evaluate the factual accuracy and citation quality of this response.

Citation Statistics: {citation_summary}
Claim Analysis: {claim_summary}

Evaluate:
1. Are factual claims properly supported by citations?
2. Are citations relevant to the claims they support?
3. Are there unsupported factual claims that need citations?
4. Overall factual accuracy and reliability

Response: {response[:2500]}

Return ONLY JSON: {{
    "score": <0-10 where 10=excellent fact-checking, 0=severe hallucinations>,
    "explanation": "<brief explanation of evaluation>",
    "issues_found": <number of potential issues>
}}"""
            
            judge_response = await self.ai_service.get_response(
                judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
            )
            
            llm_score = extract_json_score(judge_response, int(base_score))
            
            # Blend scores: 65% rule-based (citation verification + claim analysis), 35% LLM validation
            # This gives more weight to objective verification while using LLM for nuanced validation
            return base_score * 0.65 + llm_score * 0.35
        except Exception:
            # Fall back to rule-based score
            return base_score

