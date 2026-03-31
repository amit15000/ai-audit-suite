"""Fabricated citations score calculation for hallucination detection."""
from __future__ import annotations

import json
import re
from typing import Optional

from app.services.comparison.citation_enricher import CitationEnricher
from app.services.comparison.citation_source_verifier import CitationSourceVerifier
from app.services.comparison.citation_verifier import CitationVerifier, CitationVerificationResult
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.hallucination.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_score,
    clamp_score,
)


class FabricatedCitationsScorer:
    """Calculates score for detecting fabricated citations.
    
    A fabricated citation is a citation that:
    - References a URL that doesn't exist or is inaccessible
    - Points to a source that doesn't contain the claimed information
    - Uses fake or placeholder URLs
    - Is completely made up without any real source
    """

    def __init__(
        self,
        citation_verifier: CitationVerifier,
        ai_service: AIPlatformService,
        citation_enricher: Optional[CitationEnricher] = None,
        source_verifier: Optional[CitationSourceVerifier] = None
    ):
        """Initialize fabricated citations scorer.
        
        Args:
            citation_verifier: Service for verifying citations
            ai_service: Service for LLM interactions
            citation_enricher: Service for enriching citations with metadata
            source_verifier: Service for verifying citations across multiple sources
        """
        self.citation_verifier = citation_verifier
        self.ai_service = ai_service
        self.citation_enricher = citation_enricher or CitationEnricher(ai_service=ai_service)
        # Initialize source verifier with OpenAI support
        self.source_verifier = source_verifier or CitationSourceVerifier(
            ai_service=ai_service,
            use_openai=True
        )

    async def calculate_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for detecting fabricated citations (0-10).
        
        Higher score = fewer fabricated citations detected.
        
        Process:
        1. Extract all citations from the response
        2. Verify each citation (check if URL is valid and accessible)
        3. Use LLM to analyze citation patterns and detect fabrication
        4. Calculate score based on verification results and LLM analysis
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (e.g., "openai")
            use_llm: Whether to use LLM for enhanced verification (default: False)
            
        Returns:
            Score between 0-10 where:
            - 10 = No fabricated citations detected
            - 0 = Severe fabrication detected
        """
        # Step 1: Extract all citations from the response
        citations = self.citation_verifier.extract_citations(response)
        
        if not citations:
            # No citations found - can't determine if fabricated
            return 6
        
        # Step 2: Verify all citations (check if URLs are valid and accessible)
        verification_results = await self.citation_verifier.verify_all_citations(response)
        
        if not verification_results:
            return 6
        
        # Step 3: Analyze citations for fabrication
        # Calculate base score from verification results
        base_score = self._calculate_base_score_from_verification(verification_results)
        
        # Step 4: Use LLM to detect subtle fabrication patterns
        if use_llm:
            llm_analysis = await self._analyze_with_llm(
                response, 
                citations, 
                verification_results, 
                judge_platform_id
            )
            # Combine base score with LLM analysis
            final_score = self._combine_scores(base_score, llm_analysis)
        else:
            final_score = base_score
        
        return clamp_score(final_score)

    def _calculate_base_score_from_verification(
        self, verification_results: list[CitationVerificationResult]
    ) -> float:
        """Calculate base score from citation verification results.
        
        Args:
            verification_results: List of citation verification results
            
        Returns:
            Base score (0-10)
        """
        total = len(verification_results)
        if total == 0:
            return 6.0
        
        # Count valid and accessible citations
        valid_count = sum(1 for r in verification_results if r.is_valid)
        accessible_count = sum(1 for r in verification_results if r.is_accessible)
        
        # Count fabricated citations (invalid or inaccessible)
        fabricated_count = total - accessible_count
        
        # Calculate rates
        valid_rate = valid_count / total if total > 0 else 0.0
        accessible_rate = accessible_count / total if total > 0 else 0.0
        fabricated_rate = fabricated_count / total if total > 0 else 0.0
        
        # Score calculation based on fabrication rate
        if fabricated_rate == 0.0:
            # All citations are accessible - excellent
            if accessible_count >= 3:
                return 9.5
            else:
                return 9.0
        elif fabricated_rate <= 0.1:
            # Less than 10% fabricated - very good
            return 8.0
        elif fabricated_rate <= 0.3:
            # 10-30% fabricated - moderate issues
            return 6.0
        elif fabricated_rate <= 0.5:
            # 30-50% fabricated - significant issues
            return 4.0
        elif fabricated_rate <= 0.7:
            # 50-70% fabricated - severe issues
            return 2.0
        else:
            # More than 70% fabricated - critical
            return 1.0

    async def _analyze_with_llm(
        self,
        response: str,
        citations: list,
        verification_results: list[CitationVerificationResult],
        judge_platform_id: str
    ) -> dict:
        """Use LLM to analyze citations for fabrication patterns.
        
        Args:
            response: Original response text
            citations: List of extracted citations
            verification_results: Citation verification results
            judge_platform_id: Platform ID for LLM
            
        Returns:
            Dictionary with LLM analysis results
        """
        try:
            # Prepare citation data for LLM analysis
            citation_data = []
            for i, (citation, result) in enumerate(zip(citations, verification_results)):
                citation_data.append({
                    "index": i + 1,
                    "url": citation.url,
                    "context": citation.context[:200],  # First 200 chars of context
                    "is_valid": result.is_valid,
                    "is_accessible": result.is_accessible,
                    "status_code": result.status_code,
                    "error": result.error
                })
            
            # Build prompt for LLM analysis
            prompt = self._build_llm_prompt(response, citation_data, verification_results)
            
            # Call LLM
            llm_response = await self.ai_service.get_response(
                judge_platform_id,
                prompt,
                system_prompt=JUDGE_SYSTEM_PROMPT
            )
            
            # Parse LLM response
            return self._parse_llm_response(llm_response)
            
        except Exception as e:
            # If LLM analysis fails, return neutral result
            return {
                "score": 6.0,
                "fabrication_likelihood": 0.5,
                "explanation": f"LLM analysis failed: {str(e)}"
            }

    def _build_llm_prompt(
        self,
        response: str,
        citation_data: list,
        verification_results: list[CitationVerificationResult]
    ) -> str:
        """Build prompt for LLM to analyze fabricated citations.
        
        Args:
            response: Original response text
            citation_data: List of citation data dictionaries
            verification_results: Citation verification results
            
        Returns:
            Formatted prompt string
        """
        # Count statistics
        total = len(verification_results)
        accessible = sum(1 for r in verification_results if r.is_accessible)
        invalid = sum(1 for r in verification_results if not r.is_valid)
        
        # Build citation list for prompt
        citation_list = []
        for data in citation_data[:10]:  # Limit to first 10 citations
            status = "✓ Accessible" if data["is_accessible"] else "✗ Inaccessible"
            if data["error"]:
                status += f" ({data['error']})"
            citation_list.append(
                f"{data['index']}. {data['url']}\n"
                f"   Status: {status}\n"
                f"   Context: {data['context']}"
            )
        
        prompt = f"""Analyze the following citations from an AI-generated response to detect fabricated citations.

A fabricated citation is one that:
- References a URL that doesn't exist or is inaccessible
- Points to a fake or placeholder URL
- Is completely made up without any real source
- Uses suspicious patterns (e.g., example.com, test.com, placeholder URLs)

RESPONSE TEXT (first 1000 characters):
{response[:1000]}

CITATION VERIFICATION RESULTS:
Total citations found: {total}
Accessible citations: {accessible}
Invalid/inaccessible citations: {invalid}

CITATIONS:
{chr(10).join(citation_list) if citation_list else "No citations found"}

TASK:
1. Analyze each citation to determine if it appears to be fabricated
2. Look for patterns that suggest fabrication (suspicious URLs, inaccessible links, etc.)
3. Consider the context in which citations are used
4. Assess the overall likelihood of citation fabrication

Return ONLY valid JSON with this exact structure:
{{
    "score": <integer 0-10 where 10=no fabrication, 0=severe fabrication>,
    "fabrication_likelihood": <float 0.0-1.0 where 1.0=definitely fabricated>,
    "explanation": "<brief explanation of your analysis>",
    "fabricated_citations": [<list of citation indices (1-based) that appear fabricated>],
    "verified_citations": [<list of citation indices (1-based) that appear legitimate>]
}}"""
        
        return prompt

    def _parse_llm_response(self, llm_response: str) -> dict:
        """Parse LLM response to extract analysis results.
        
        Args:
            llm_response: Raw LLM response text
            
        Returns:
            Dictionary with parsed results
        """
        # Try to extract JSON from response
        json_match = re.search(r'\{.*?\}', llm_response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                return {
                    "score": float(result.get("score", 6.0)),
                    "fabrication_likelihood": float(result.get("fabrication_likelihood", 0.5)),
                    "explanation": str(result.get("explanation", "")),
                    "fabricated_citations": result.get("fabricated_citations", []),
                    "verified_citations": result.get("verified_citations", [])
                }
            except (json.JSONDecodeError, ValueError, KeyError):
                pass
        
        # Fallback: try to extract score using utility function
        score = extract_json_score(llm_response, 6)
        return {
            "score": float(score),
            "fabrication_likelihood": 0.5,
            "explanation": "Could not fully parse LLM response",
            "fabricated_citations": [],
            "verified_citations": []
        }

    def _combine_scores(self, base_score: float, llm_analysis: dict) -> float:
        """Combine base verification score with LLM analysis.
        
        Args:
            base_score: Score from verification (0-10)
            llm_analysis: LLM analysis results
            
        Returns:
            Combined score (0-10)
        """
        llm_score = llm_analysis.get("score", 6.0)
        fabrication_likelihood = llm_analysis.get("fabrication_likelihood", 0.5)
        
        # Weighted combination:
        # - 60% base score (objective verification)
        # - 40% LLM score (pattern analysis)
        combined = (base_score * 0.6) + (llm_score * 0.4)
        
        # Apply fabrication likelihood adjustment
        # Higher likelihood = lower score (penalty)
        # Lower likelihood = higher score (bonus)
        # Max adjustment: ±2 points
        adjustment = (0.5 - fabrication_likelihood) * 4.0  # Range: -2.0 to +2.0
        combined = combined + adjustment
        
        return max(0.0, min(10.0, combined))
    
    def _build_metadata_dict(self, enriched) -> dict:
        """Build metadata dictionary, only including fields with valid values.
        
        Args:
            enriched: EnrichedCitation object
            
        Returns:
            Dictionary with only non-null, valid metadata fields
        """
        metadata = {}
        
        # Title field removed - not including in output
        
        # Only add authors if they exist and are valid
        if enriched.authors and len(enriched.authors) > 0:
            # Filter out invalid author entries
            valid_authors = []
            for author in enriched.authors:
                if author and isinstance(author, str) and len(author.strip()) > 5:
                    # Check if it looks like a real name (not just "by", "et al", etc.)
                    author_clean = author.strip()
                    if not any(word in author_clean.lower() for word in ['by', 'http', 'www', 'doi']):
                        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', author_clean):
                            valid_authors.append(author_clean)
            if valid_authors:
                metadata["authors"] = valid_authors
        
        # Only add year if it's a valid 4-digit year
        if enriched.year and isinstance(enriched.year, int):
            if 1900 <= enriched.year <= 2100:
                metadata["year"] = enriched.year
        
        # Only add DOI if it exists
        if enriched.doi and enriched.doi.strip():
            metadata["doi"] = enriched.doi.strip()
        
        # Always include source_type (default to "unknown" if not set)
        metadata["source_type"] = enriched.source_type or "unknown"
        
        return metadata
    
    async def get_detailed_verification_report(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> dict:
        """Get detailed verification report for all citations in JSON format.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (e.g., "openai")
            use_llm: Whether to use LLM for enhanced verification (default: False)
            
        Returns:
            Dictionary with detailed verification report:
            {
                "total_citations": int,
                "verified_count": int,
                "fabricated_count": int,
                "score": int (0-10),
                "citations": [
                    {
                        "index": int,
                        "original_citation": str,
                        "verified": bool,
                        "verification_status": str,  # "Not verified" or "Verified via {source_name}"
                        "verified_source_url": str | null,  # Link to verified source, or null if not verified
                        "metadata": {
                            "title": str | null,
                            "authors": list[str] | null,
                            "year": int | null,
                            "doi": str | null,
                            "source_type": str
                        }
                    }
                ]
            }
        """
        # Step 1: Extract all citations
        citations = self.citation_verifier.extract_citations(response)
        
        if not citations:
            return {
                "total_citations": 0,
                "verified_count": 0,
                "fabricated_count": 0,
                "score": 6,
                "citations": []
            }
        
        # Step 2: Enrich and verify each citation
        citation_reports = []
        for i, citation in enumerate(citations):
            # For title-based citations, extract title from citation.url (which contains the title)
            if citation.citation_type in ["title", "paper_name"]:
                # The citation.url actually contains the paper title
                citation_text = citation.url
                # Try to extract more metadata from context
                enriched = self.citation_enricher.extract_citation_metadata(
                    citation_text,
                    citation.context
                )
                # Set the title explicitly
                if not enriched.title:
                    enriched.title = citation_text
                enriched.original_url = citation_text
            else:
                # For URL/DOI citations, use normal enrichment
                enriched = await self.citation_enricher.enrich_citation(
                    citation.url,
                    citation.context
                )
            
            # Verify citation across multiple sources using OpenAI (searches everywhere automatically)
            verification_report = await self.source_verifier.verify_citation(
                enriched,
                judge_platform_id=judge_platform_id
            )
            
            # Find the best verified source (if any)
            verified_source = None
            if verification_report.verified:
                # Find the source with highest confidence that verified
                verified_sources = [
                    r for r in verification_report.verification_results 
                    if r.verified
                ]
                if verified_sources:
                    # Sort by confidence and get the best one
                    verified_sources.sort(key=lambda x: x.confidence, reverse=True)
                    verified_source = verified_sources[0]
            
            # Build simplified verification info
            if verification_report.verified and verified_source:
                verification_status = f"Verified via {verified_source.source_name}"
                verification_link = verified_source.source_url
            else:
                verification_status = "Not verified"
                verification_link = None
            
            citation_reports.append({
                "index": i + 1,
                "original_citation": citation.url,
                "verified": verification_report.verified,
                "verification_status": verification_status,
                "verified_source_url": verification_link,
                "metadata": self._build_metadata_dict(enriched)
            })
        
        # Step 3: Calculate statistics
        verified_count = sum(1 for r in citation_reports if r["verified"])
        fabricated_count = len(citation_reports) - verified_count
        
        # Step 4: Calculate score
        if use_llm:
            # Use existing calculate_score method with LLM
            score = await self.calculate_score(response, judge_platform_id, use_llm=True)
        else:
            # Calculate score from verification results
            if len(citation_reports) == 0:
                score = 6
            else:
                verified_rate = verified_count / len(citation_reports)
                if verified_rate == 1.0:
                    score = 9 if verified_count >= 3 else 8
                elif verified_rate >= 0.9:
                    score = 8
                elif verified_rate >= 0.7:
                    score = 7
                elif verified_rate >= 0.5:
                    score = 6
                elif verified_rate >= 0.3:
                    score = 4
                elif verified_rate >= 0.1:
                    score = 2
                else:
                    score = 1
        
        return {
            "total_citations": len(citation_reports),
            "verified_count": verified_count,
            "fabricated_count": fabricated_count,
            "score": clamp_score(score),
            "citations": citation_reports
        }
