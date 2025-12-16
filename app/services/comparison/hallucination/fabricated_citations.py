"""Fabricated citations score calculation for hallucination detection."""
from __future__ import annotations

import re

from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.hallucination.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_score,
    clamp_score,
)


class FabricatedCitationsScorer:
    """Calculates score for detecting fabricated citations."""

    def __init__(self, citation_verifier: CitationVerifier, ai_service: AIPlatformService):
        """Initialize fabricated citations scorer.
        
        Args:
            citation_verifier: Service for verifying citations
            ai_service: Service for LLM interactions
        """
        self.citation_verifier = citation_verifier
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for detecting fabricated citations (0-10).
        
        Uses actual citation verification to check if URLs are valid and accessible.
        Higher score = fewer fabricated citations detected.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced verification (default: False)
            
        Returns:
            Score between 0-10
        """
        # Extract and verify all citations
        verification_results = await self.citation_verifier.verify_all_citations(response)
        citation_stats = self.citation_verifier.get_citation_statistics(verification_results)
        
        if citation_stats['total'] == 0:
            # No citations found - can't detect fabrication
            return 6
        
        # Calculate base score from verification results
        base_score = self._calculate_base_score(citation_stats)
        
        # Apply pattern-based adjustments
        base_score = self._apply_pattern_adjustments(
            response, verification_results, citation_stats, base_score
        )
        
        # Optional LLM enhancement for complex cases
        if use_llm and (self._count_suspicious_urls(verification_results) > 0 or citation_stats['total'] > 5):
            base_score = await self._apply_llm_enhancement(
                verification_results, base_score, judge_platform_id
            )
        
        return clamp_score(base_score)

    def _calculate_base_score(self, citation_stats: dict) -> float:
        """Calculate base score from citation statistics.
        
        Uses a more sophisticated scoring that considers:
        - Invalid rate (primary indicator of fabrication)
        - Accessibility rate (secondary validation)
        - Absolute numbers (context matters)
        
        Args:
            citation_stats: Statistics from citation verification
            
        Returns:
            Base score (0-10)
        """
        if citation_stats['total'] == 0:
            return 6.0  # Can't detect fabrication without citations
        
        accessibility_rate = citation_stats['accessibility_rate']
        invalid_count = citation_stats['invalid']
        accessible_count = citation_stats['accessible']
        total_count = citation_stats['total']
        invalid_rate = invalid_count / total_count if total_count > 0 else 0
        
        # Primary scoring based on invalid rate (strongest indicator of fabrication)
        if invalid_rate > 0.5:
            # More than half invalid - strong evidence of fabrication
            if invalid_count >= 3:
                return 1.0  # Critical: many fabricated citations
            else:
                return 2.0  # Severe: significant fabrication
        elif invalid_rate > 0.3:
            # 30-50% invalid - likely fabrication
            return 3.5  # Poor: substantial fabrication detected
        elif invalid_rate > 0.1:
            # 10-30% invalid - some issues
            if accessible_count >= 2:
                return 6.0  # Acceptable: some invalid but also valid ones
            else:
                return 5.0  # Borderline: mostly invalid
        elif invalid_rate > 0:
            # <10% invalid - minor issues
            if accessibility_rate >= 0.9:
                return 9.0  # Excellent: almost all valid
            elif accessibility_rate >= 0.7:
                return 8.0  # Very good: most valid
            else:
                return 7.0  # Good: mostly valid
        else:
            # No invalid citations
            if accessibility_rate >= 0.9:
                if accessible_count >= 3:
                    return 9.5  # Excellent: many valid citations
                else:
                    return 9.0  # Excellent: all valid
            elif accessibility_rate >= 0.7:
                return 8.5  # Very good: most accessible
            else:
                return 7.5  # Good: some accessibility issues but no fabrication

    def _apply_pattern_adjustments(
        self,
        response: str,
        verification_results: list,
        citation_stats: dict,
        base_score: float
    ) -> float:
        """Apply pattern-based adjustments to score.
        
        Detects various patterns that indicate fabricated citations:
        - Suspicious URL patterns
        - Citation-text mismatches
        - Duplicate/identical citations
        - Citation format inconsistencies
        
        Args:
            response: Response text
            verification_results: Citation verification results
            citation_stats: Citation statistics
            base_score: Current base score
            
        Returns:
            Adjusted score
        """
        score = base_score
        
        # Adjustment 1: Suspicious URL patterns (strong indicator of fabrication)
        suspicious_count = self._count_suspicious_urls(verification_results)
        if suspicious_count > 0:
            suspicious_rate = suspicious_count / citation_stats['total']
            if suspicious_rate > 0.5:
                score -= 2.5  # Severe penalty: majority are suspicious
            elif suspicious_rate > 0.3:
                score -= 1.5  # Strong penalty: many suspicious
            else:
                score -= min(1.0, suspicious_count * 0.5)  # Moderate penalty
        
        # Adjustment 2: Citation-text mismatch (citations mentioned but not properly linked)
        citation_mentions = [
            'cited', 'reference', 'source', 'according to', 'as per',
            'as stated in', 'as reported by', 'per', 'from'
        ]
        mentions = sum(1 for mention in citation_mentions if mention in response.lower())
        actual_citations = citation_stats['total']
        
        if actual_citations > 0:
            mention_to_citation_ratio = mentions / actual_citations
            if mention_to_citation_ratio > 3.0:
                score -= 1.5  # Strong mismatch: many mentions, few actual citations
            elif mention_to_citation_ratio > 2.0:
                score -= 0.5  # Moderate mismatch
        elif mentions > 5:
            score -= 1.0  # Many citation mentions but no actual citations
        
        # Adjustment 3: Duplicate/identical citations (potential fabrication pattern)
        url_counts = {}
        for result in verification_results:
            normalized_url = self._normalize_citation_url(result.citation.url)
            url_counts[normalized_url] = url_counts.get(normalized_url, 0) + 1
        
        duplicate_count = sum(1 for count in url_counts.values() if count > 1)
        if duplicate_count > 0:
            # Some duplication is normal, but excessive duplication is suspicious
            if duplicate_count >= 3:
                score -= 1.0  # Penalty: excessive duplication
            elif duplicate_count >= 2:
                score -= 0.3  # Small penalty: some duplication
        
        # Adjustment 4: Citation format quality (proper formats indicate legitimacy)
        academic_pattern = r'\([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*,\s*\d{4}\)'
        academic_citations = len(re.findall(academic_pattern, response))
        
        # DOI patterns
        doi_pattern = r'doi[:\s]+10\.\d+/[^\s\)]+'
        doi_citations = len(re.findall(doi_pattern, response, re.IGNORECASE))
        
        # Proper citation formats indicate legitimacy
        proper_formats = academic_citations + doi_citations
        if proper_formats > 0:
            if proper_formats >= 3:
                score += 0.5  # Bonus: multiple proper formats
            else:
                score += 0.2  # Small bonus: some proper formats
        
        # Adjustment 5: Citation distribution (all citations clustered = suspicious)
        if len(verification_results) > 2:
            positions = [r.citation.position for r in verification_results]
            position_range = max(positions) - min(positions)
            text_length = len(response)
            
            if text_length > 500:  # Only check for longer texts
                distribution_ratio = position_range / text_length
                if distribution_ratio < 0.1:  # Citations clustered in <10% of text
                    score -= 0.5  # Penalty: suspicious clustering
        
        return score

    def _normalize_citation_url(self, url: str) -> str:
        """Normalize URL for duplicate detection."""
        url = url.lower().strip()
        # Remove protocol
        url = re.sub(r'^https?://', '', url)
        # Remove www.
        url = re.sub(r'^www\.', '', url)
        # Remove trailing slashes and fragments
        url = url.rstrip('/')
        if '#' in url:
            url = url.split('#')[0]
        return url

    def _count_suspicious_urls(self, verification_results: list) -> int:
        """Count suspicious URLs in verification results.
        
        Args:
            verification_results: Citation verification results
            
        Returns:
            Count of suspicious URLs
        """
        suspicious_patterns = [
            'example.com', 'test.com', 'placeholder', 'fake', 'localhost', '127.0.0.1'
        ]
        suspicious_count = 0
        for result in verification_results:
            url_lower = result.citation.url.lower()
            if any(pattern in url_lower for pattern in suspicious_patterns):
                suspicious_count += 1
        return suspicious_count

    async def _apply_llm_enhancement(
        self,
        verification_results: list,
        base_score: float,
        judge_platform_id: str
    ) -> float:
        """Apply LLM enhancement to score calculation.
        
        Uses LLM to analyze citation patterns and detect subtle fabrication indicators.
        
        Args:
            verification_results: Citation verification results
            base_score: Current base score
            judge_platform_id: Platform ID for LLM
            
        Returns:
            Enhanced score
        """
        try:
            # Organize verification results for analysis
            invalid_urls = [
                r.citation.url for r in verification_results if not r.is_accessible
            ][:10]
            valid_urls = [
                r.citation.url for r in verification_results if r.is_accessible
            ][:10]
            
            # Extract suspicious patterns
            suspicious_urls = [
                r.citation.url for r in verification_results
                if any(pattern in r.citation.url.lower() 
                      for pattern in ['example.com', 'test.com', 'placeholder', 'fake', 'localhost'])
            ][:5]
            
            # Build comprehensive prompt
            prompt = f"""Analyze these citations to detect potential fabrication:

Valid/Accessible URLs ({len(valid_urls)}): {', '.join(valid_urls[:5]) if valid_urls else 'None'}
Invalid/Inaccessible URLs ({len(invalid_urls)}): {', '.join(invalid_urls[:5]) if invalid_urls else 'None'}
Suspicious Pattern URLs ({len(suspicious_urls)}): {', '.join(suspicious_urls) if suspicious_urls else 'None'}

Evaluate:
1. Do URLs look legitimate or fabricated?
2. Are there patterns suggesting systematic fabrication?
3. What's the overall likelihood of citation fabrication?

Return ONLY JSON: {{
    "score": <0-10 where 10=no fabrication, 0=severe fabrication>,
    "explanation": "<brief explanation>",
    "fabrication_likelihood": <0.0-1.0>
}}"""
            
            judge_response = await self.ai_service.get_response(
                judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
            )
            
            llm_score = extract_json_score(judge_response, int(base_score))
            
            # Blend scores: 75% verification-based (objective), 25% LLM pattern analysis
            # Higher weight on verification since it's more objective
            return base_score * 0.75 + llm_score * 0.25
        except Exception:
            return base_score

