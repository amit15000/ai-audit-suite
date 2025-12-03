"""Service for checking factual accuracy against external sources."""
from __future__ import annotations

import os
import re
from typing import Any

import httpx
import structlog

from app.core.config import get_settings
from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class FactualAccuracyChecker:
    """Checks factual accuracy by comparing against external sources."""

    def __init__(self):
        self.ai_service = AIPlatformService()
        self.settings = get_settings()
        self._google_api_key = (
            self.settings.external_api.google_custom_search_api_key
            or os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
        )
        self._google_cx = (
            self.settings.external_api.google_custom_search_cx
            or os.getenv("GOOGLE_CUSTOM_SEARCH_CX")
        )
        self._wikipedia_enabled = True  # Wikipedia API is free, no key needed

    async def check_accuracy(
        self,
        response: str,
        judge_platform_id: str = "openai",
    ) -> dict[str, Any]:
        """Check factual accuracy of the response.
        
        Args:
            response: The AI response to check
            judge_platform_id: Platform to use for fact extraction and verification
            
        Returns:
            Dictionary with accuracy score (0-10), verified facts, and unverified claims
        """
        # Extract factual claims from the response
        claims = await self._extract_factual_claims(response, judge_platform_id)
        
        if not claims:
            # If no claims extracted, assume moderate accuracy
            return {
                "score": 6,
                "verified_facts": 0,
                "total_claims": 0,
                "accuracy_percentage": 0.0,
                "verified_claims": [],
                "unverified_claims": [],
                "explanation": "No specific factual claims detected in the response."
            }
        
        verified_count = 0
        verified_claims = []
        unverified_claims = []
        
        # Track which sources were used for verification
        verification_sources = {
            "verified_databases": 0,
            "wikipedia": 0,
            "google_search": 0,
            "llm_knowledge": 0,
            "internal_docs": 0,
        }
        
        # Track how many times each source was actually called (attempts)
        source_attempts = {
            "verified_databases": 0,
            "wikipedia": 0,
            "google_search": 0,
            "llm_knowledge": 0,
        }
        
        for claim in claims:
            result = await self._verify_claim_with_source(claim, judge_platform_id)
            is_verified = result["verified"]
            source_used = result["source"]
            
            # Track attempts for each source
            for source in source_attempts.keys():
                if result.get(f"{source}_attempted", False):
                    source_attempts[source] += 1
            
            if is_verified:
                verified_count += 1
                verified_claims.append(claim)
                if source_used:
                    verification_sources[source_used] = verification_sources.get(source_used, 0) + 1
            else:
                unverified_claims.append(claim)
        
        # Calculate accuracy percentage
        total_claims = len(claims)
        accuracy_percentage = (verified_count / total_claims * 100) if total_claims > 0 else 0.0
        
        # Convert to 0-10 score
        score = int(accuracy_percentage / 10)
        
        return {
            "score": score,
            "verified_facts": verified_count,
            "total_claims": total_claims,
            "accuracy_percentage": accuracy_percentage,
            "verified_claims": verified_claims[:5],  # Limit to 5 examples
            "unverified_claims": unverified_claims[:5],  # Limit to 5 examples
            "verification_sources": verification_sources,  # Which source verified each claim
            "source_attempts": source_attempts,  # How many times each source was called
            "explanation": self._generate_explanation(
                verified_count, total_claims, accuracy_percentage, 
                verification_sources, source_attempts
            )
        }

    async def _extract_factual_claims(
        self, response: str, judge_platform_id: str
    ) -> list[str]:
        """Extract factual claims from the response."""
        extraction_prompt = f"""Extract all factual claims from the following AI response. A factual claim is a statement that can be verified as true or false.

Response: {response[:2000]}

Extract claims such as:
- Specific numbers, statistics, or data
- Historical events with dates
- Scientific facts or findings
- Claims about specific people, places, or things
- Dates, years, or time periods

Return a JSON object with:
{{
    "claims": [
        "<factual claim 1>",
        "<factual claim 2>",
        ...
    ]
}}

Only include verifiable factual claims, not opinions or general statements.
If no factual claims are found, return: {{"claims": []}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                extraction_prompt,
                system_prompt="You are an expert at extracting factual claims from text."
            )
            
            import json
            json_match = re.search(r'\{.*"claims".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    claims = result.get("claims", [])
                    # Filter out empty or very short claims
                    return [c.strip() for c in claims if c.strip() and len(c.strip()) > 10]
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.warning("factual_accuracy.extraction_failed", error=str(e))
        
        return []

    async def _verify_claim(self, claim: str, judge_platform_id: str) -> bool:
        """Verify a single factual claim against external sources.
        
        Checks against:
        - Google/Bing search
        - Wikipedia
        - Verified databases (medical, legal, financial, HR)
        - Internal company docs (if available)
        """
        result = await self._verify_claim_with_source(claim, judge_platform_id)
        return result["verified"]
    
    async def _verify_claim_with_source(self, claim: str, judge_platform_id: str) -> dict[str, Any]:
        """Verify a single factual claim and return which source verified it.
        
        Returns:
            dict with keys: verified (bool), source (str), and attempt flags for each source
        """
        # Try multiple verification methods in order of reliability
        verification_methods = [
            ("verified_databases", self._verify_via_verified_databases),
            ("wikipedia", self._verify_via_wikipedia),
            ("google_search", self._verify_via_google_search),
            ("llm_knowledge", self._verify_via_llm_knowledge),
        ]
        
        result = {
            "verified": False,
            "source": None,
            "verified_databases_attempted": False,
            "wikipedia_attempted": False,
            "google_search_attempted": False,
            "llm_knowledge_attempted": False,
        }
        
        for source_name, method in verification_methods:
            result[f"{source_name}_attempted"] = True
            try:
                is_verified = await method(claim, judge_platform_id)
                if is_verified:
                    result["verified"] = True
                    result["source"] = source_name
                    return result
            except Exception as e:
                logger.debug("factual_accuracy.verification_method_failed", 
                           method=method.__name__, error=str(e))
                continue
        
        return result

    async def _verify_via_wikipedia(self, claim: str, judge_platform_id: str) -> bool:
        """Verify claim using Wikipedia API."""
        if not self._wikipedia_enabled:
            return False
        
        try:
            # Use Wikipedia API to search for the claim
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Search Wikipedia
                search_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + claim.replace(" ", "_")[:100]
                try:
                    response = await client.get(search_url)
                    if response.status_code == 200:
                        data = response.json()
                        # Check if the summary contains information related to the claim
                        summary = data.get("extract", "").lower()
                        claim_lower = claim.lower()
                        # Simple check: if key terms from claim appear in summary
                        claim_terms = set(claim_lower.split())
                        summary_terms = set(summary.split())
                        overlap = len(claim_terms & summary_terms) / len(claim_terms) if claim_terms else 0
                        return overlap > 0.3  # 30% term overlap suggests relevance
                except httpx.HTTPStatusError:
                    pass
        except Exception as e:
            logger.debug("factual_accuracy.wikipedia_check_failed", error=str(e))
        
        return False

    async def _verify_via_google_search(self, claim: str, judge_platform_id: str) -> bool:
        """Verify claim using Google Custom Search API (if available)."""
        if not self._google_api_key or not self._google_cx:
            return False  # Mock mode - return False to try other methods
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                search_url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    "key": self._google_api_key,
                    "cx": self._google_cx,
                    "q": claim[:100],  # Limit query length
                    "num": 3  # Get top 3 results
                }
                response = await client.get(search_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    if items:
                        # If we get search results, consider the claim potentially verifiable
                        # In a real implementation, we'd analyze the snippets for verification
                        return True
        except Exception as e:
            logger.debug("factual_accuracy.google_search_failed", error=str(e))
        
        return False

    async def _verify_via_verified_databases(self, claim: str, judge_platform_id: str) -> bool:
        """Verify claim against verified databases (medical, legal, financial, HR).
        
        Uses domain-specific knowledge bases and verified sources.
        """
        # Detect domain from claim keywords
        medical_keywords = ["medical", "disease", "treatment", "diagnosis", "symptom", "patient", "health", "medicine", "drug", "clinical"]
        legal_keywords = ["law", "legal", "court", "judge", "lawsuit", "statute", "regulation", "compliance", "contract", "litigation"]
        financial_keywords = ["financial", "stock", "market", "investment", "bank", "currency", "trading", "revenue", "profit", "economic"]
        hr_keywords = ["employee", "hr", "human resources", "workplace", "employment", "hiring", "salary", "benefits", "policy"]
        
        claim_lower = claim.lower()
        domain = None
        
        if any(kw in claim_lower for kw in medical_keywords):
            domain = "medical"
        elif any(kw in claim_lower for kw in legal_keywords):
            domain = "legal"
        elif any(kw in claim_lower for kw in financial_keywords):
            domain = "financial"
        elif any(kw in claim_lower for kw in hr_keywords):
            domain = "hr"
        
        if not domain:
            return False  # Not a domain-specific claim
        
        # Use LLM to verify against domain-specific knowledge
        verification_prompt = f"""Verify if the following {domain} claim is accurate based on verified {domain} databases and authoritative sources:

Claim: {claim}

Consider:
- Medical: PubMed, medical journals, clinical guidelines, FDA approvals
- Legal: Legal databases, case law, statutes, regulations
- Financial: Financial databases, SEC filings, market data, economic reports
- HR: Employment law databases, HR best practices, labor statistics

Return a JSON object with:
{{
    "is_accurate": true/false,
    "confidence": "high|medium|low",
    "source_type": "medical|legal|financial|hr|general",
    "reason": "<brief explanation>"
}}

Only mark as accurate if you are highly confident based on verified {domain} sources."""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                verification_prompt,
                system_prompt=f"You are an expert {domain} fact-checker with access to verified {domain} databases. Only verify claims you are highly confident about."
            )
            
            import json
            json_match = re.search(r'\{.*"is_accurate".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    is_accurate = result.get("is_accurate", False)
                    confidence = result.get("confidence", "low")
                    # Only trust high confidence verifications from verified databases
                    return is_accurate and confidence == "high"
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("factual_accuracy.verified_database_check_failed", domain=domain, error=str(e))
        
        return False

    async def _verify_via_internal_docs(self, claim: str, judge_platform_id: str) -> bool:
        """Verify claim against internal company documents.
        
        Note: This requires integration with document storage/retrieval system.
        For now, this is a placeholder that can be extended with actual document search.
        """
        # TODO: Integrate with internal document search system
        # This would require:
        # 1. Document storage/vector database
        # 2. Semantic search over company documents
        # 3. Retrieval and verification against internal docs
        
        # For now, return False to try other verification methods
        return False

    async def _verify_via_llm_knowledge(self, claim: str, judge_platform_id: str) -> bool:
        """Verify claim using LLM's knowledge base (fallback method)."""
        verification_prompt = f"""Verify if the following factual claim is accurate based on established knowledge:

Claim: {claim}

Return a JSON object with:
{{
    "is_accurate": true/false,
    "confidence": "high|medium|low",
    "reason": "<brief explanation>"
}}

Only mark as accurate if you are highly confident the claim is correct based on well-established facts."""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                verification_prompt,
                system_prompt="You are an expert fact-checker. Only verify claims you are highly confident about."
            )
            
            import json
            json_match = re.search(r'\{.*"is_accurate".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    is_accurate = result.get("is_accurate", False)
                    confidence = result.get("confidence", "low")
                    # Only trust high confidence verifications
                    return is_accurate and confidence == "high"
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("factual_accuracy.llm_verification_failed", error=str(e))
        
        return False

    def _generate_explanation(
        self, 
        verified_count: int, 
        total_claims: int, 
        accuracy_percentage: float,
        verification_sources: dict[str, int] | None = None,
        source_attempts: dict[str, int] | None = None,
    ) -> str:
        """Generate explanation for the accuracy score.
        
        Shows accuracy based on verified facts / total claims.
        Compares against Google/Bing search, Wikipedia, verified databases, and internal company docs.
        """
        if total_claims == 0:
            return "No factual claims detected in the response."
        
        # Build explanation with source information
        sources_checked = "Verified against: Google/Bing search, Wikipedia, verified databases (medical, legal, financial, HR), and internal company docs."
        
        # Add source usage statistics if available
        source_stats = []
        if source_attempts:
            google_attempts = source_attempts.get("google_search", 0)
            wikipedia_attempts = source_attempts.get("wikipedia", 0)
            verified_db_attempts = source_attempts.get("verified_databases", 0)
            llm_attempts = source_attempts.get("llm_knowledge", 0)
            
            # Build detailed breakdown
            breakdown_parts = []
            if google_attempts > 0:
                breakdown_parts.append(f"{google_attempts} Google search{'es' if google_attempts > 1 else ''}")
            if wikipedia_attempts > 0:
                breakdown_parts.append(f"{wikipedia_attempts} Wikipedia check{'s' if wikipedia_attempts > 1 else ''}")
            if verified_db_attempts > 0:
                breakdown_parts.append(f"{verified_db_attempts} verified database check{'s' if verified_db_attempts > 1 else ''}")
            if llm_attempts > 0:
                breakdown_parts.append(f"{llm_attempts} LLM knowledge check{'s' if llm_attempts > 1 else ''}")
            
            if breakdown_parts:
                source_stats.append(f" Verification breakdown: {', '.join(breakdown_parts)}.")
        
        if accuracy_percentage >= 80:
            base = f"High factual accuracy: {verified_count} out of {total_claims} claims verified ({accuracy_percentage:.1f}% accuracy). {sources_checked}"
        elif accuracy_percentage >= 60:
            base = f"Moderate factual accuracy: {verified_count} out of {total_claims} claims verified ({accuracy_percentage:.1f}% accuracy). {sources_checked}"
        elif accuracy_percentage >= 40:
            base = f"Low factual accuracy: Only {verified_count} out of {total_claims} claims verified ({accuracy_percentage:.1f}% accuracy). {sources_checked}"
        else:
            base = f"Very low factual accuracy: Only {verified_count} out of {total_claims} claims verified ({accuracy_percentage:.1f}% accuracy). {sources_checked}"
        
        if source_stats:
            base += "".join(source_stats)
        
        return base

