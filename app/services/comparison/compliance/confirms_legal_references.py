"""Confirms legal references score calculation for compliance detection."""
from __future__ import annotations

import re

from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.compliance.utils import JUDGE_SYSTEM_PROMPT, extract_json_bool


class ConfirmsLegalReferencesScorer:
    """Checks if legal references are confirmed."""

    def __init__(self, citation_verifier: CitationVerifier, ai_service: AIPlatformService):
        """Initialize confirms legal references scorer.
        
        Args:
            citation_verifier: Service for verifying citations
            ai_service: Service for LLM interactions
        """
        self.citation_verifier = citation_verifier
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if legal references are confirmed (Yes/No).
        
        Verifies if legal references (cases, statutes, regulations) in the response
        are valid and can be confirmed.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if legal references are confirmed, False otherwise
        """
        # Check for legal reference patterns
        legal_patterns = [
            r'case\s+no\.', r'docket', r'statute', r'regulation', r'law\s+no\.',
            r'sec\.', r'section\s+\d+', r'chapter\s+\d+', r'usc\s+\d+', r'cfr\s+\d+',
            r'court\s+case', r'legal\s+precedent', r'judicial', r'jurisdiction'
        ]
        
        legal_references = []
        for pattern in legal_patterns:
            matches = re.finditer(pattern, response, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 50)
                end = min(len(response), match.end() + 50)
                context = response[start:end]
                legal_references.append(context)
        
        if len(legal_references) == 0:
            # No legal references found, can't confirm
            return False
        
        # Check if legal references are in accessible citations
        verification_results = await self.citation_verifier.verify_all_citations(response)
        
        # Check for legal domain indicators in accessible citations
        legal_domain_indicators = [
            'court', 'legal', 'law', 'statute', 'regulation', 'case', 'docket',
            'jurisdiction', 'precedent', 'judicial'
        ]
        
        legal_citations = []
        for result in verification_results:
            if result.is_accessible:
                citation_text = (result.citation.url + ' ' + (result.citation.text or '')).lower()
                if any(indicator in citation_text for indicator in legal_domain_indicators):
                    legal_citations.append(result)
        
        # If we have legal references and accessible legal citations, confirmation is successful
        result = len(legal_citations) > 0 and len(legal_references) > 0
        
        # Optional LLM enhancement
        if use_llm and len(legal_references) > 0:
            try:
                prompt = f"""Check if legal references in this response are confirmed:

Response: {response[:2000]}

Found {len(legal_references)} legal references, {len(legal_citations)} accessible legal citations.

Return ONLY JSON: {{"confirms": <true/false>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                result = extract_json_bool(judge_response, "confirms", result)
            except Exception:
                pass
        
        return result

