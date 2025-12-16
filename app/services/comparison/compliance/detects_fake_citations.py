"""Detects fake citations score calculation for compliance detection."""
from __future__ import annotations

from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.compliance.utils import JUDGE_SYSTEM_PROMPT, extract_json_bool


class DetectsFakeCitationsScorer:
    """Checks if fake citations are detected."""

    def __init__(self, citation_verifier: CitationVerifier, ai_service: AIPlatformService):
        """Initialize detects fake citations scorer.
        
        Args:
            citation_verifier: Service for verifying citations
            ai_service: Service for LLM interactions
        """
        self.citation_verifier = citation_verifier
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if fake citations are detected (Yes/No).
        
        Detects if there are fabricated or fake citations in the response.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if fake citations are detected, False otherwise
        """
        # Extract and verify citations
        verification_results = await self.citation_verifier.verify_all_citations(response)
        citation_stats = self.citation_verifier.get_citation_statistics(verification_results)
        
        if citation_stats['total'] == 0:
            # No citations found, can't detect fake ones
            return False
        
        # Check for suspicious patterns
        suspicious_patterns = [
            'example.com', 'test.com', 'placeholder', 'fake', 'localhost',
            '127.0.0.1', 'dummy', 'sample', 'mock'
        ]
        
        suspicious_count = 0
        for result in verification_results:
            url_lower = result.citation.url.lower()
            if any(pattern in url_lower for pattern in suspicious_patterns):
                suspicious_count += 1
        
        # Check invalid/inaccessible citations
        invalid_rate = citation_stats['invalid'] / citation_stats['total'] if citation_stats['total'] > 0 else 0
        
        # If many citations are invalid or suspicious, fake citations are detected
        result = (invalid_rate > 0.3) or (suspicious_count > 0)
        
        # Optional LLM enhancement
        if use_llm and citation_stats['total'] > 0:
            try:
                invalid_urls = [r.citation.url for r in verification_results if not r.is_accessible][:5]
                suspicious_urls = [
                    r.citation.url for r in verification_results
                    if any(pattern in r.citation.url.lower() for pattern in suspicious_patterns)
                ][:5]
                
                prompt = f"""Check if fake citations are detected in this response:

Response: {response[:2000]}

Invalid/inaccessible URLs: {', '.join(invalid_urls) if invalid_urls else 'None'}
Suspicious URLs: {', '.join(suspicious_urls) if suspicious_urls else 'None'}

Return ONLY JSON: {{"detects": <true/false>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                result = extract_json_bool(judge_response, "detects", result)
            except Exception:
                pass
        
        return result

