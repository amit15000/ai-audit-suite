"""External fact check sub-score calculation for hallucination detection."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import warnings
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import structlog
from openai import OpenAI

# Suppress duckduckgo_search package rename warnings
if not sys.warnoptions:
    warnings.simplefilter("ignore", RuntimeWarning)
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

from app.core.config import get_settings
from app.domain.schemas import (
    ExternalFactCheckClaim,
    ExternalFactCheckResult,
)

logger = structlog.get_logger(__name__)


def _get_openai_client() -> OpenAI | None:
    """Get OpenAI client using OPENAI_API_KEY from environment.
    
    Returns:
        OpenAI client if API key is available, None otherwise
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


async def _call_openai(prompt: str, system_prompt: str | None = None) -> str:
    """Call OpenAI API directly.
    
    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        
    Returns:
        Response text from OpenAI
        
    Raises:
        ValueError: If API key is not set or API call fails
    """
    client = _get_openai_client()
    if not client:
        raise ValueError("OPENAI_API_KEY is not set in environment variables")
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    try:
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                timeout=30,
            )
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise ValueError(f"OpenAI API call failed: {str(e)}")


@dataclass
class Claim:
    """Simple representation of a factual claim."""

    id: str
    claim: str
    original_span: str


@dataclass
class Evidence:
    """Evidence source from web search."""

    url: str
    title: str
    snippet: str
    domain: str
    source_rank: int


class ClaimExtractor:
    """Extracts factual claims from response text using LLM."""

    def __init__(self, use_llm: bool = True):
        """Initialize claim extractor.
        
        Args:
            use_llm: Whether to use LLM for extraction (default: True)
        """
        self.use_llm = use_llm

    async def extract_claims(self, response: str, max_claims: int = 20) -> list[Claim]:
        """Extract factual claims from response using LLM.
        
        Args:
            response: Response text to analyze
            max_claims: Maximum number of claims to extract
            
        Returns:
            List of Claim objects
        """
        if self.use_llm:
            try:
                claims = await self._extract_claims_llm(response, max_claims)
                if claims:
                    return claims
            except Exception as e:
                logger.warning("llm_extraction_failed", error=str(e))
        
        # Return empty list if LLM fails
        return []

    async def _extract_claims_llm(self, response: str, max_claims: int) -> list[Claim]:
        """Extract claims using LLM.
        
        Args:
            response: Response text
            max_claims: Maximum claims to extract
            
        Returns:
            List of Claim objects
        """
        system_prompt = """You are an expert at extracting factual claims from text. Extract atomic, verifiable factual claims.

Return ONLY valid JSON array:
[
    {
        "id": "c1",
        "claim": "exact claim text",
        "original_span": "original sentence/context"
    }
]"""

        prompt = f"""Extract all factual claims from the following text. Focus on verifiable facts (dates, numbers, statistics, historical events, scientific facts, etc.).

Text:
{response}

Extract up to {max_claims} claims. Return ONLY the JSON array, no other text."""

        try:
            response_text = await _call_openai(prompt, system_prompt=system_prompt)
            
            # Extract JSON array
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                claims_data = json.loads(json_match.group(0))
                claims = []
                for idx, claim_data in enumerate(claims_data[:max_claims], 1):
                    claims.append(Claim(
                        id=claim_data.get("id", f"c{idx}"),
                        claim=claim_data.get("claim", ""),
                        original_span=claim_data.get("original_span", ""),
                    ))
                
                logger.info("llm_extraction_success", claims_count=len(claims))
                
                # Log each extracted claim
                for claim in claims:
                    logger.info(
                        "claim_extracted",
                        claim_id=claim.id,
                        claim=claim.claim,
                        original_span=claim.original_span[:150] if claim.original_span else "",
                    )
                
                return claims
        except Exception as e:
            logger.warning("llm_claim_extraction_parse_error", error=str(e))
        
        return []


class EvidenceRetriever:
    """Retrieves evidence from web search using DuckDuckGo."""

    def __init__(self, timeout: int = 10, top_k: int = 5):
        """Initialize evidence retriever.
        
        Args:
            timeout: Request timeout in seconds
            top_k: Number of top results to retrieve
        """
        self.timeout = timeout
        self.top_k = top_k
        self._cache: dict[str, tuple[list[Evidence], float]] = {}
        self._cache_ttl = 3600  # 1 hour

    async def retrieve_evidence(self, claim: str) -> list[Evidence]:
        """Retrieve evidence for a claim from web search.
        
        Args:
            claim: Claim text to search for
            
        Returns:
            List of Evidence objects
        """
        # Check cache
        cache_key = claim.lower().strip()
        if cache_key in self._cache:
            cached_results, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return cached_results
        
        try:
            evidence = await self._retrieve_duckduckgo(claim)
            
            # Cache results
            self._cache[cache_key] = (evidence, time.time())
            
            logger.info(
                "evidence_retrieved",
                claim=claim[:100],
                evidence_count=len(evidence),
                sources=[e.url for e in evidence[:3]],
            )
            
            return evidence
        except Exception as e:
            logger.warning("evidence_retrieval_failed", claim=claim[:100], error=str(e))
            return []

    async def _retrieve_duckduckgo(self, claim: str) -> list[Evidence]:
        """Retrieve evidence using DuckDuckGo search.
        
        Args:
            claim: Claim text to search for
            
        Returns:
            List of Evidence objects
        """
        try:
            # Import with warning suppression
            DDGS = None
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    from duckduckgo_search import DDGS as DuckDDGS  # type: ignore[import-untyped, import-not-found]
                    DDGS = DuckDDGS
            except ImportError:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        from ddgs import DDGS as DuckDDGS  # type: ignore[import-untyped, import-not-found]
                        DDGS = DuckDDGS
                except ImportError:
                    logger.error("search_library_not_installed", 
                                hint="Install with: pip install duckduckgo-search")
                    return []
            
            if DDGS is None:
                return []
            
            # Run search in executor
            loop = asyncio.get_event_loop()
            
            def search_sync():
                """Synchronous search with warning suppression."""
                import sys
                import io
                
                class StderrFilter:
                    def __init__(self, original):
                        self.original = original
                    
                    def write(self, text):
                        if "duckduckgo_search" in text and "renamed" in text:
                            return
                        self.original.write(text)
                    
                    def flush(self):
                        self.original.flush()
                    
                    def __getattr__(self, name):
                        return getattr(self.original, name)
                
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    original_stderr = sys.stderr
                    try:
                        sys.stderr = StderrFilter(original_stderr)
                        with DDGS() as ddgs:
                            results = list(ddgs.text(
                                claim,
                                max_results=self.top_k,
                                safesearch="moderate"
                            ))
                            return results or []
                    finally:
                        sys.stderr = original_stderr
            
            # Execute search with timeout
            try:
                search_results = await asyncio.wait_for(
                    loop.run_in_executor(None, search_sync),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                logger.warning("duckduckgo_timeout", claim=claim[:50])
                return []
            
            if not search_results:
                return []
            
            # Process results with quality filtering
            evidence_list = []
            rank = 1
            for result in search_results:
                url = result.get("href") or result.get("link") or ""
                title = result.get("title") or ""
                snippet = result.get("body") or result.get("snippet") or ""
                
                if not url or not title:
                    continue
                
                domain = urlparse(url).netloc.lower() if url else ""
                
                # Filter out low-quality sources
                if self._is_low_quality_source(domain, url):
                    continue
                
                evidence_list.append(Evidence(
                    url=url,
                    title=title,
                    snippet=snippet,
                    domain=domain,
                    source_rank=rank,
                ))
                rank += 1
                
                if len(evidence_list) >= self.top_k:
                    break
            
            return evidence_list
        except Exception as e:
            logger.error("duckduckgo_error", error=str(e), claim=claim[:50])
            return []
    
    def _is_low_quality_source(self, domain: str, url: str) -> bool:
        """Check if source is low-quality and should be filtered out.
        
        Args:
            domain: Domain name
            url: Full URL
            
        Returns:
            True if source should be filtered out
        """
        # Blacklisted domains
        blacklisted_domains = [
            "zhidao.baidu.com",
            "baidu.com",
            "zhihu.com",
            "sogou.com",
            "support.google.com",
            "support.microsoft.com",
            "help.",
            "docs.",
            "forum.",
        ]
        
        # Check domain blacklist
        for blacklisted in blacklisted_domains:
            if blacklisted in domain:
                return True
        
        # Filter out support/documentation pages
        url_lower = url.lower()
        if any(pattern in url_lower for pattern in ["/support/", "/help/", "/docs/", "/documentation/", "/guide/"]):
            # Allow Stack Overflow and reputable sources
            if not any(reputable in domain for reputable in ["stackoverflow.com", "stackexchange.com", "wikipedia.org", "gov", "edu"]):
                return True
        
        return False


class ClaimEnricher:
    """Enriches claims with context from the full response."""

    async def enrich_claims(self, claims: list[Claim], full_response: str) -> list[Claim]:
        """Enrich claims with context from the full response.
        
        Args:
            claims: List of extracted claims
            full_response: Original full response text
            
        Returns:
            List of enriched claims with context
        """
        if not claims:
            return claims
        
        system_prompt = """You are an expert at enriching factual claims with context. Given a list of claims and the full response text, modify each claim to include necessary context so it can be understood independently.

Rules:
1. If a claim uses pronouns (it, the city, this, etc.), replace them with the actual entity from context
2. If a claim is vague, add specific details from the response
3. Keep the core factual content of each claim
4. Make claims self-contained and clear

Return ONLY valid JSON array with the same structure:
[
    {
        "id": "c1",
        "claim": "enriched claim with context",
        "original_span": "original span"
    }
]"""

        # Build claims list for prompt
        claims_text = "\n".join([f"{claim.id}: {claim.claim}" for claim in claims])
        
        prompt = f"""Given the following claims extracted from a response, enrich them with context from the full response so they are self-contained and clear.

Full Response:
{full_response}

Extracted Claims:
{claims_text}

For each claim:
- Replace pronouns (it, the city, this, etc.) with actual entities from the response
- Add necessary context to make the claim clear and verifiable
- Keep the core factual content

Return ONLY the JSON array with enriched claims, maintaining the same IDs."""

        try:
            response_text = await _call_openai(prompt, system_prompt=system_prompt)
            
            # Extract JSON array
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                enriched_data = json.loads(json_match.group(0))
                
                # Create mapping of enriched claims
                enriched_map = {item.get("id"): item.get("claim", "") for item in enriched_data}
                
                # Update claims with enriched versions
                enriched_claims = []
                for claim in claims:
                    enriched_claim_text = enriched_map.get(claim.id, claim.claim)
                    enriched_claims.append(Claim(
                        id=claim.id,
                        claim=enriched_claim_text,
                        original_span=claim.original_span,
                    ))
                    
                    if enriched_claim_text != claim.claim:
                        logger.info(
                            "claim_enriched",
                            claim_id=claim.id,
                            original_claim=claim.claim,
                            enriched_claim=enriched_claim_text,
                        )
                
                return enriched_claims
        except Exception as e:
            logger.warning("claim_enrichment_failed", error=str(e))
            # Return original claims if enrichment fails
            return claims
        
        return claims


class LLMFactChecker:
    """Verifies claims using OpenAI with web knowledge."""

    def __init__(self, timeout: int = 30):
        """Initialize LLM fact checker.
        
        Args:
            timeout: Verification timeout in seconds
        """
        self.timeout = timeout

    async def verify_claim(self, claim: Claim) -> dict[str, Any]:
        """Verify a claim using OpenAI's web knowledge.
        
        Args:
            claim: Claim to verify
            
        Returns:
            Verification result with is_true, explanation, and sources_used (domains)
        """
        system_prompt = """You are a strict fact-checker with access to web knowledge. Verify factual claims using your knowledge base.

CRITICAL RULES:
1. Only mark as TRUE if the claim is clearly supported by your web knowledge
2. Mark as FALSE if the claim is refuted, contradicted, or insufficient evidence
3. Be conservative - when in doubt, mark as FALSE
4. Provide clear explanation of your reasoning
5. List the SPECIFIC PAGE URLs where this information can be found (e.g., https://en.wikipedia.org/wiki/New_York_City, https://www.nytimes.com/article/..., etc.)
6. Provide actual clickable URLs, not just domain names

Return ONLY valid JSON:
{
    "is_true": true|false,
    "explanation": "Brief explanation of your reasoning and how you would verify this",
    "sources_used": ["https://en.wikipedia.org/wiki/SpecificPage", "https://www.nytimes.com/2020/..."]
}"""

        prompt = f"""Verify the following factual claim using your web knowledge.

Claim: {claim.claim}

Analyze whether the claim is:
- TRUE: The claim is factually correct based on your knowledge
- FALSE: The claim is incorrect, refuted, or cannot be verified

Provide:
1. Your verdict (is_true: true or false)
2. Explanation of your reasoning
3. List of SPECIFIC PAGE URLs where this information can be verified (e.g., https://en.wikipedia.org/wiki/New_York_City, https://www.census.gov/data/..., https://www.nytimes.com/2020/...)
   - Provide full URLs with paths, not just domains
   - Use actual URLs where this specific information would be found
   - Make URLs clickable and specific to the claim

Return ONLY valid JSON with is_true (boolean), explanation, and sources_used (array of full URLs)."""

        try:
            response = await asyncio.wait_for(
                _call_openai(prompt, system_prompt=system_prompt),
                timeout=self.timeout,
            )
            
            # Extract JSON - be more specific to avoid matching too much
            json_match = re.search(r'\{[^{}]*"is_true"[^{}]*\}', response, re.DOTALL)
            if not json_match:
                # Try a more lenient match
                json_match = re.search(r'\{.*?"is_true".*?"sources_used".*?\}', response, re.DOTALL)
            
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    is_true = bool(result.get("is_true", False))
                    explanation = result.get("explanation", "")
                    sources_used = result.get("sources_used", [])
                    
                    # Validate sources_used are URLs (strings)
                    valid_sources = []
                    if isinstance(sources_used, list):
                        for source in sources_used:
                            if isinstance(source, str) and source.strip():
                                # Ensure it's a valid URL
                                url = source.strip()
                                # Add https:// if missing
                                if not url.startswith(("http://", "https://")):
                                    url = "https://" + url
                                # Validate it looks like a URL
                                if "." in url and ("http://" in url or "https://" in url):
                                    valid_sources.append(url)
                    
                    logger.info(
                        "claim_verification_complete",
                        claim_id=claim.id,
                        claim=claim.claim,
                        is_true=is_true,
                        explanation=explanation,
                        sources_count=len(valid_sources),
                        sources_used=valid_sources,
                    )
                    
                    return {
                        "is_true": is_true,
                        "explanation": explanation,
                        "sources_used": valid_sources,
                    }
                except json.JSONDecodeError as je:
                    logger.warning("json_parse_error", claim_id=claim.id, error=str(je), response_preview=response[:200])
            else:
                logger.warning("no_json_found", claim_id=claim.id, response_preview=response[:200])
        except asyncio.TimeoutError:
            logger.warning("verification_timeout", claim_id=claim.id)
        except Exception as e:
            logger.warning("verification_error", claim_id=claim.id, error=str(e), error_type=type(e).__name__, exc_info=True)
        
        # Default to False on failure
        return {
            "is_true": False,
            "explanation": "Verification failed or timed out",
            "sources_used": [],
        }


class ExternalFactCheckScorer:
    """Orchestrates external fact checking and computes sub-score using LLM."""

    def __init__(self):
        """Initialize external fact check scorer."""
        settings = get_settings().external_fact_check
        
        self.claim_extractor = ClaimExtractor(
            use_llm=settings.claim_extraction_use_llm,
        )
        self.claim_enricher = ClaimEnricher()
        self.fact_checker = LLMFactChecker(
            timeout=settings.verification_timeout,
        )
        self.max_claims = settings.max_claims_per_response

    async def calculate_sub_score(
        self,
        response: str,
    ) -> ExternalFactCheckResult:
        """Calculate external fact check sub-score.
        
        Args:
            response: Response text to evaluate
            
        Returns:
            ExternalFactCheckResult with sub-score and detailed claims
        """
        settings = get_settings().external_fact_check
        
        if not settings.enabled:
            logger.info("external_fact_check_disabled")
            return ExternalFactCheckResult(
                sub_score_name="External Fact Check",
                score=50,  # Neutral score
                coverage=0.0,
                claims=[],
                sources_used=[],
                notes=["External fact check is disabled"],
            )
        
        # Step 1: Extract claims using LLM
        logger.info("starting_claim_extraction", response_length=len(response), max_claims=self.max_claims)
        claims = await self.claim_extractor.extract_claims(response, self.max_claims)
        
        if not claims:
            logger.info("no_claims_extracted", response_length=len(response))
            return ExternalFactCheckResult(
                sub_score_name="External Fact Check",
                score=50,  # Neutral score when no claims
                coverage=0.0,
                claims=[],
                sources_used=[],
                notes=["No factual claims detected in response"],
            )
        
        logger.info("claims_extraction_complete", total_claims=len(claims))
        
        # Step 2: Enrich claims with context from full response
        logger.info("starting_claim_enrichment", total_claims=len(claims))
        enriched_claims = await self.claim_enricher.enrich_claims(claims, response)
        logger.info("claims_enrichment_complete", total_claims=len(enriched_claims))
        
        # Step 3: Verify enriched claims using OpenAI (with concurrency control)
        logger.info("starting_claim_verification", total_claims=len(enriched_claims))
        semaphore_verify = asyncio.Semaphore(3)  # Max 3 concurrent verifications
        
        async def verify_claim_safe(claim: Claim) -> tuple[Claim, dict[str, Any]]:
            async with semaphore_verify:
                logger.info("verifying_claim", claim_id=claim.id, claim=claim.claim[:100])
                verification = await self.fact_checker.verify_claim(claim)
                return (claim, verification)
        
        verification_results = await asyncio.gather(
            *[verify_claim_safe(claim) for claim in enriched_claims],
            return_exceptions=True,
        )
        
        logger.info("claim_verification_complete", total_verifications=len(verification_results))
        
        # Step 4: Process results and compute score
        # Use original claims for display, but enriched claims were verified
        verified_claims = []
        true_count = 0
        false_count = 0
        all_sources = set()
        
        logger.info("processing_verification_results", total_results=len(verification_results))
        
        for result in verification_results:
            # Handle exceptions
            if isinstance(result, BaseException):
                logger.error("claim_verification_exception", error=str(result), error_type=type(result).__name__)
                continue
            
            if not isinstance(result, tuple) or len(result) != 2:
                logger.warning("invalid_verification_result", result_type=type(result).__name__)
                continue
            
            claim, verification = result
            is_true = verification.get("is_true", False)
            explanation = verification.get("explanation", "")
            sources_used = verification.get("sources_used", [])  # These are domains from OpenAI
            
            # Collect all source domains
            for domain in sources_used:
                all_sources.add(domain)
            
            # Log each claim's verification result
            logger.info(
                "claim_result",
                claim_id=claim.id,
                claim=claim.claim,
                is_true=is_true,
                explanation=explanation,
                sources_used=sources_used,
            )
            
            # Count results
            if is_true:
                true_count += 1
            else:
                false_count += 1
            
            # Convert sources to schema format (URLs from OpenAI)
            from app.domain.schemas import ExternalFactCheckEvidence
            from urllib.parse import urlparse
            
            evidence_schema = []
            for idx, source_url in enumerate(sources_used):
                # Parse URL to get domain
                try:
                    parsed = urlparse(source_url)
                    domain = parsed.netloc or parsed.path.split("/")[0] if parsed.path else ""
                    # Remove www. prefix
                    if domain.startswith("www."):
                        domain = domain[4:]
                except:
                    domain = source_url.split("/")[0] if "/" in source_url else source_url
                
                # Extract page title from URL or use domain
                page_title = domain
                if "/" in source_url:
                    # Try to extract meaningful page name from URL
                    path_parts = [p for p in source_url.split("/") if p and p not in ["http:", "https:", ""]]
                    if path_parts:
                        # Use last meaningful part as title hint
                        last_part = path_parts[-1].replace("-", " ").replace("_", " ").title()
                        if len(last_part) > 3:
                            page_title = f"{domain} - {last_part}"
                
                evidence_schema.append(ExternalFactCheckEvidence(
                    url=source_url,  # Full URL
                    title=page_title,
                    snippet=explanation[:200] if explanation else "",
                    source_rank=idx + 1,
                    domain=domain,
                ))
            
            # Store explanation in notes (since schema doesn't have explanation field)
            claim_notes = [explanation] if explanation else []
            
            # Convert to schema format
            verified_claims.append(ExternalFactCheckClaim(
                id=claim.id,
                claim=claim.claim,
                claim_type="general",
                original_span=claim.original_span,
                risk="medium",
                verdict="SUPPORTED" if is_true else "REFUTED",
                confidence=1.0 if is_true else 0.0,
                top_evidence=evidence_schema,
            ))
            
            # Store explanation separately for test display (we'll add it to a custom dict)
            # For now, we'll log it and the test can extract from logs or we add it to result notes
        
        # Step 5: Compute score (0-100)
        # Simple scoring: percentage of claims that are TRUE
        total_claims = len(enriched_claims)
        if total_claims == 0:
            score = 50  # Neutral
        else:
            # Score = (true_count / total_claims) * 100
            score = (true_count / total_claims) * 100
        
        # Coverage: percentage of claims that were verified (all claims are verified)
        coverage = 1.0 if total_claims > 0 else 0.0
        
        # Generate notes
        notes = []
        if true_count > 0:
            notes.append(f"{true_count} claim(s) verified as TRUE")
        if false_count > 0:
            notes.append(f"{false_count} claim(s) verified as FALSE")
        
        # Store explanations for each claim (we'll add them to a custom attribute)
        # Since we can't modify the schema easily, we'll include key info in the result notes
        claim_explanations = {}
        for result in verification_results:
            if isinstance(result, tuple) and len(result) == 3:
                claim, verification, _ = result
                explanation = verification.get("explanation", "")
                if explanation:
                    claim_explanations[claim.id] = explanation
        
        logger.info(
            "external_fact_check_complete",
            total_claims=total_claims,
            true_count=true_count,
            false_count=false_count,
            score=score,
            coverage=coverage,
            sources_count=len(all_sources),
        )
        
        # Log summary
        logger.info(
            "verification_summary",
            claims_summary=[
                {
                    "id": claim.id,
                    "claim": claim.claim[:80],
                    "is_true": next(
                        (r[1].get("is_true", False) for r in verification_results 
                         if isinstance(r, tuple) and len(r) == 3 and r[0].id == claim.id),
                        False
                    ),
                }
                for claim in enriched_claims
            ],
        )
        
        return ExternalFactCheckResult(
            sub_score_name="External Fact Check",
            score=int(score),
            coverage=coverage,
            claims=verified_claims,
            sources_used=list(all_sources),
            notes=notes,
        )
