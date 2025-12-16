"""Google/Bing/Wikipedia score calculation for accuracy detection."""
from __future__ import annotations

import re

from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.accuracy.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_score,
    clamp_score,
)


class GoogleBingWikipediaScorer:
    """Calculates Google/Bing/Wikipedia verification score."""

    def __init__(self, citation_verifier: CitationVerifier, ai_service: AIPlatformService):
        """Initialize Google/Bing/Wikipedia scorer.
        
        Args:
            citation_verifier: Service for verifying citations
            ai_service: Service for LLM interactions
        """
        self.citation_verifier = citation_verifier
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for Google/Bing search Wikipedia verification (0-10).
        
        Checks if the response contains information that can be verified against
        Wikipedia and general web search sources.
        Higher score = better accuracy against Wikipedia/web sources.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Score between 0-10
        """
        # Extract citations and URLs
        verification_results = await self.citation_verifier.verify_all_citations(response)
        citation_stats = self.citation_verifier.get_citation_statistics(verification_results)
        
        # Check for Wikipedia references
        wikipedia_patterns = [
            r'wikipedia\.org',
            r'wikipedia',
            r'en\.wikipedia',
            r'wiki/',
        ]
        wikipedia_count = sum(
            1 for pattern in wikipedia_patterns
            if re.search(pattern, response, re.IGNORECASE)
        )
        
        # Check for general web search indicators
        web_search_indicators = [
            'according to', 'research shows', 'studies indicate',
            'as reported by', 'source:', 'reference:', 'cited in'
        ]
        web_search_count = sum(
            1 for indicator in web_search_indicators
            if indicator in response.lower()
        )
        
        # Base score calculation
        base_score = 6  # Neutral starting point
        
        # Wikipedia references boost score
        if wikipedia_count > 0:
            base_score += min(2, wikipedia_count * 0.5)
        
        # Web search indicators boost score
        if web_search_count > 2:
            base_score += min(2, (web_search_count - 2) * 0.3)
        
        # Citation accessibility boosts score
        if citation_stats['total'] > 0:
            accessibility_rate = citation_stats['accessibility_rate']
            if accessibility_rate >= 0.8:
                base_score += 1
            elif accessibility_rate >= 0.5:
                base_score += 0.5
        
        # Check for factual claims that can be verified
        factual_claims = [
            r'\b\d{4}\b',  # Years
            r'\b\d+%',  # Percentages
            r'\b\d+\.\d+',  # Decimals
        ]
        factual_count = sum(
            len(re.findall(pattern, response)) for pattern in factual_claims
        )
        if factual_count > 3:
            base_score += min(1, factual_count * 0.1)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Evaluate how well this response can be verified against Google/Bing search and Wikipedia sources:

Response: {response[:2000]}

Return ONLY JSON: {{"score": <0-10>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                llm_score = extract_json_score(judge_response, int(base_score))
                # Blend scores (70% rule-based, 30% LLM)
                base_score = int(base_score * 0.7 + llm_score * 0.3)
            except Exception:
                pass
        
        return clamp_score(base_score)

