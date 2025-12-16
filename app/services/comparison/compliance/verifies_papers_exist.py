"""Verifies papers exist score calculation for compliance detection."""
from __future__ import annotations

import re

from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.compliance.utils import JUDGE_SYSTEM_PROMPT, extract_json_bool


class VerifiesPapersExistScorer:
    """Checks if papers existence is verified."""

    def __init__(self, citation_verifier: CitationVerifier, ai_service: AIPlatformService):
        """Initialize verifies papers exist scorer.
        
        Args:
            citation_verifier: Service for verifying citations
            ai_service: Service for LLM interactions
        """
        self.citation_verifier = citation_verifier
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if papers existence is verified (Yes/No).
        
        Verifies if academic papers and research documents referenced in the response
        actually exist and are accessible.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if papers existence is verified, False otherwise
        """
        # Extract citations
        verification_results = await self.citation_verifier.verify_all_citations(response)
        
        # Check for paper-like citations
        paper_patterns = [
            r'doi:', r'doi\s*[:\s]+', r'pubmed', r'pmid', r'arxiv', r'issn', r'isbn',
            r'journal', r'proceedings', r'conference', r'paper', r'research\s+paper'
        ]
        
        paper_citations = []
        for result in verification_results:
            citation_text = result.citation.url.lower() + ' ' + (result.citation.text or '').lower()
            if any(re.search(pattern, citation_text, re.IGNORECASE) for pattern in paper_patterns):
                paper_citations.append(result)
        
        if len(paper_citations) == 0:
            # No paper citations found, can't verify
            return False
        
        # Check if papers are accessible
        accessible_papers = sum(1 for result in paper_citations if result.is_accessible)
        accessibility_rate = accessible_papers / len(paper_citations) if paper_citations else 0
        
        # If most papers are accessible, verification is successful
        result = accessibility_rate >= 0.7
        
        # Optional LLM enhancement
        if use_llm and len(paper_citations) > 0:
            try:
                prompt = f"""Check if academic papers in this response are verified to exist:

Response: {response[:2000]}

Found {len(paper_citations)} paper citations, {accessible_papers} accessible.

Return ONLY JSON: {{"verifies": <true/false>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                result = extract_json_bool(judge_response, "verifies", result)
            except Exception:
                pass
        
        return result

