"""Checks URLs exist score calculation for compliance detection."""
from __future__ import annotations

from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.compliance.utils import JUDGE_SYSTEM_PROMPT, extract_json_bool


class ChecksUrlsExistScorer:
    """Checks if URLs existence is verified."""

    def __init__(self, citation_verifier: CitationVerifier, ai_service: AIPlatformService):
        """Initialize checks URLs exist scorer.
        
        Args:
            citation_verifier: Service for verifying citations
            ai_service: Service for LLM interactions
        """
        self.citation_verifier = citation_verifier
        self.ai_service = ai_service

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if URLs existence is checked (Yes/No).
        
        Verifies if URLs in the response are checked for existence and accessibility.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if URLs existence is checked, False otherwise
        """
        # Extract and verify URLs
        verification_results = await self.citation_verifier.verify_all_citations(response)
        
        if len(verification_results) == 0:
            # No URLs found, can't check
            return False
        
        # Check if URLs are accessible
        accessible_count = sum(1 for result in verification_results if result.is_accessible)
        total_urls = len(verification_results)
        
        # If most URLs are accessible, checking is successful
        result = (accessible_count / total_urls) >= 0.7 if total_urls > 0 else False
        
        # Optional LLM enhancement
        if use_llm and total_urls > 0:
            try:
                prompt = f"""Check if URLs in this response are verified to exist:

Response: {response[:2000]}

Found {total_urls} URLs, {accessible_count} accessible.

Return ONLY JSON: {{"checks": <true/false>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                result = extract_json_bool(judge_response, "checks", result)
            except Exception:
                pass
        
        return result

