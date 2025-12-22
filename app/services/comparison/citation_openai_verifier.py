"""Simplified citation verification using OpenAI's web search capabilities."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

import structlog

from app.services.comparison.citation_enricher import EnrichedCitation
from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


@dataclass
class OpenAIVerificationResult:
    """Result of verifying a citation using OpenAI."""
    
    verified: bool
    source_url: Optional[str] = None  # Complete link to the verified source
    source_name: Optional[str] = None  # Name of the source/platform where found
    confidence: float = 0.0  # 0.0-1.0 confidence in verification
    explanation: Optional[str] = None
    error: Optional[str] = None


class CitationOpenAIVerifier:
    """Simplified citation verifier using OpenAI's web search and knowledge."""
    
    def __init__(self, ai_service: AIPlatformService):
        """Initialize OpenAI citation verifier.
        
        Args:
            ai_service: AI service for OpenAI interactions
        """
        self.ai_service = ai_service
    
    async def verify_citation_with_openai(
        self, 
        citation: EnrichedCitation,
        judge_platform_id: str = "openai"
    ) -> OpenAIVerificationResult:
        """Verify a citation using OpenAI's web search and knowledge.
        
        This method uses OpenAI to intelligently search the web and verify
        if the citation actually exists across multiple platforms.
        
        Args:
            citation: Enriched citation to verify
            judge_platform_id: Platform ID for OpenAI (default: "openai")
            
        Returns:
            OpenAIVerificationResult with verification status
        """
        try:
            # Build comprehensive prompt for OpenAI
            prompt = self._build_verification_prompt(citation)
            
            system_prompt = """You are an expert citation verifier with access to web search capabilities.
Your task is to verify if a citation actually exists by searching across multiple academic and web platforms.

VERIFICATION PROCESS:
1. Search for the citation using the provided information (DOI, title, URL, etc.)
2. Check multiple sources: Google Scholar, PubMed, DOI resolver, Semantic Scholar, arXiv, ResearchGate, Academia.edu, SSRN, Crossref, and general web search
3. Verify that the citation actually exists (not just that a URL opens, but that the actual paper/resource is there)
4. If found, provide the complete URL to the verified source
5. If not found after thorough search, mark as not verified

CRITICAL RULES:
- A citation is ONLY verified if you can find the actual paper/resource, not just a page that says "no results"
- Check for negative indicators like "no results found", "not found", "404", "produced no results"
- Look for positive indicators like abstract, authors, published date, DOI, full text, etc.
- Be thorough - search multiple platforms before concluding it doesn't exist
- Provide the complete, clickable URL where the citation was found

Return ONLY valid JSON with this exact structure:
{
    "verified": true|false,
    "source_url": "https://complete-url-to-verified-source.com/...",
    "source_name": "google_scholar|pubmed|doi|semantic_scholar|arxiv|researchgate|academia|ssrn|crossref|web",
    "confidence": 0.0-1.0,
    "explanation": "Brief explanation of where and how you found (or didn't find) the citation"
}"""
            
            # Call OpenAI
            response = await self.ai_service.get_response(
                judge_platform_id,
                prompt,
                system_prompt=system_prompt
            )
            
            # Parse response
            return self._parse_openai_response(response, citation)
            
        except Exception as e:
            logger.error("OpenAI citation verification failed", error=str(e))
            return OpenAIVerificationResult(
                verified=False,
                error=f"OpenAI verification failed: {str(e)}"
            )
    
    def _build_verification_prompt(self, citation: EnrichedCitation) -> str:
        """Build prompt for OpenAI to verify citation.
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "Verify if the following citation actually exists by searching across multiple platforms:",
            "",
            "CITATION INFORMATION:"
        ]
        
        # Prioritize title if available (for title-based citations)
        if citation.title:
            prompt_parts.append(f"  Title: {citation.title}")
            prompt_parts.append("  ⚠️ IMPORTANT: This is a TITLE-BASED citation. Search by paper title!")
        
        if citation.original_url:
            # If original_url is not a URL but a title, note it
            if not citation.original_url.startswith(('http://', 'https://', 'www.')):
                prompt_parts.append(f"  Paper Name/Title: {citation.original_url}")
            else:
                prompt_parts.append(f"  Original URL/Citation: {citation.original_url}")
        
        if citation.doi:
            prompt_parts.append(f"  DOI: {citation.doi}")
        
        if citation.authors:
            prompt_parts.append(f"  Authors: {', '.join(citation.authors)}")
        
        if citation.year:
            prompt_parts.append(f"  Year: {citation.year}")
        
        if citation.source_type:
            prompt_parts.append(f"  Source Type: {citation.source_type}")
        
        if citation.extracted_text:
            prompt_parts.append(f"  Context: {citation.extracted_text[:300]}")
        
        prompt_parts.extend([
            "",
            "SEARCH STRATEGY:",
            "  - If DOI provided: Search DOI resolver first, then other platforms",
            "  - If Title/Paper Name provided: Search Google Scholar, Semantic Scholar, PubMed, arXiv by title",
            "  - If Authors provided: Combine title + authors in search",
            "  - Search across ALL relevant platforms:",
            "    • Google Scholar - primary for title-based searches",
            "    • Semantic Scholar - AI-powered academic search",
            "    • PubMed - medical/biological research",
            "    • arXiv - preprints",
            "    • ResearchGate - academic social network",
            "    • Academia.edu - academic papers",
            "    • SSRN - social science research",
            "    • Crossref - DOI registry",
            "    • DOI Resolver (doi.org) - if DOI available",
            "    • General web search - as fallback",
            "",
            "VERIFICATION REQUIREMENTS:",
            "  1. For TITLE-BASED citations: Search using the exact paper title",
            "  2. Check if the citation actually exists (not just URL accessibility)",
            "  3. Look for the actual paper/resource, not error pages or 'no results'",
            "  4. Match title, authors, and year if provided",
            "  5. If found, provide the complete URL to the verified source",
            "  6. If not found after thorough search across multiple platforms, mark as not verified",
            "",
            "Return JSON with verification result."
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_openai_response(
        self, 
        response: str, 
        citation: EnrichedCitation
    ) -> OpenAIVerificationResult:
        """Parse OpenAI response to extract verification result.
        
        Args:
            response: OpenAI response text
            citation: Original citation being verified
            
        Returns:
            OpenAIVerificationResult
        """
        # Try to extract JSON from response
        json_match = re.search(r'\{.*?\}', response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                return OpenAIVerificationResult(
                    verified=bool(result.get("verified", False)),
                    source_url=result.get("source_url"),
                    source_name=result.get("source_name"),
                    confidence=float(result.get("confidence", 0.0)),
                    explanation=result.get("explanation")
                )
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning("Failed to parse OpenAI JSON response", error=str(e))
        
        # Fallback: try to infer from text response
        response_lower = response.lower()
        if any(word in response_lower for word in ["verified", "found", "exists", "confirmed"]):
            # Try to extract URL from response
            url_match = re.search(r'https?://[^\s\)\]\>]+', response)
            source_url = url_match.group(0) if url_match else None
            
            return OpenAIVerificationResult(
                verified=True,
                source_url=source_url,
                source_name="web",
                confidence=0.7,
                explanation=response[:200]
            )
        else:
            return OpenAIVerificationResult(
                verified=False,
                error="Could not verify citation - no matching results found"
            )
