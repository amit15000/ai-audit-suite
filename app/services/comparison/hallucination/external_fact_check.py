"""External fact check sub-score calculation for hallucination detection."""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from app.core.config import get_settings
from app.domain.schemas import (
    ExternalFactCheckClaim,
    ExternalFactCheckEvidence,
    ExternalFactCheckResult,
)
from app.services.comparison.hallucination.utils import JUDGE_SYSTEM_PROMPT
from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


@dataclass
class Claim:
    """Internal representation of a factual claim."""

    id: str
    claim: str
    claim_type: str
    original_span: str
    risk: str  # low, medium, high


@dataclass
class Evidence:
    """Internal representation of evidence from web search."""

    url: str
    title: str
    snippet: str
    source_rank: int
    domain: str
    full_text: str | None = None


class ClaimExtractor:
    """Extracts atomic factual claims from response text."""

    def __init__(self, use_llm: bool = False, ai_service: AIPlatformService | None = None):
        """Initialize claim extractor.
        
        Args:
            use_llm: Whether to use LLM for extraction (default: False, uses rule-based)
            ai_service: AI service for LLM extraction (required if use_llm=True)
        """
        self.use_llm = use_llm
        self.ai_service = ai_service

    async def extract_claims(self, response: str, max_claims: int = 20) -> list[Claim]:
        """Extract factual claims from response.
        
        Args:
            response: Response text to analyze
            max_claims: Maximum number of claims to extract
            
        Returns:
            List of Claim objects
        """
        if self.use_llm and self.ai_service:
            return await self._extract_claims_llm(response, max_claims)
        else:
            return self._extract_claims_rule_based(response, max_claims)

    def _extract_claims_rule_based(self, response: str, max_claims: int) -> list[Claim]:
        """Extract claims using rule-based approach.
        
        Args:
            response: Response text
            max_claims: Maximum claims to extract
            
        Returns:
            List of Claim objects
        """
        claims = []
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', response)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        claim_id = 1
        for sentence in sentences:
            if claim_id > max_claims:
                break
                
            # Filter out questions
            if sentence.strip().endswith('?'):
                continue
                
            # Filter out opinion indicators
            opinion_indicators = [
                "i think", "i believe", "in my opinion", "i feel", "i guess",
                "probably", "maybe", "perhaps", "might", "could be"
            ]
            if any(indicator in sentence.lower() for indicator in opinion_indicators):
                continue
            
            # Extract declarative statements
            if self._is_factual_claim(sentence):
                claim_type = self._classify_claim_type(sentence)
                risk = self._assess_claim_risk(sentence, claim_type)
                
                claims.append(Claim(
                    id=f"c{claim_id}",
                    claim=sentence,
                    claim_type=claim_type,
                    original_span=sentence,
                    risk=risk
                ))
                claim_id += 1
        
        return claims

    def _is_factual_claim(self, sentence: str) -> bool:
        """Check if sentence contains a factual claim.
        
        Args:
            sentence: Sentence to check
            
        Returns:
            True if sentence appears to be a factual claim
        """
        # Look for factual indicators
        factual_patterns = [
            r'\d+',  # Contains numbers
            r'\b(?:is|are|was|were|has|have|had)\b',  # Declarative verbs
            r'\b(?:in|on|during|since|until)\s+\d{4}\b',  # Dates
            r'\b(?:according to|research shows|studies indicate|data suggests)\b',  # Citations
        ]
        
        return any(re.search(pattern, sentence, re.IGNORECASE) for pattern in factual_patterns)

    def _classify_claim_type(self, sentence: str) -> str:
        """Classify the type of claim.
        
        Args:
            sentence: Claim sentence
            
        Returns:
            Claim type: date, number, entity, or general
        """
        if re.search(r'\b(?:in|on|during|since|until)\s+\d{4}\b', sentence):
            return "date"
        elif re.search(r'\d+[%]?', sentence):
            return "number"
        elif re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', sentence):
            return "entity"
        else:
            return "general"

    def _assess_claim_risk(self, sentence: str, claim_type: str) -> str:
        """Assess the risk level of a claim.
        
        Args:
            sentence: Claim sentence
            claim_type: Type of claim
            
        Returns:
            Risk level: low, medium, or high
        """
        # High-risk indicators
        high_risk_patterns = [
            r'\d+%',  # Percentages
            r'\b(?:study|research|survey|analysis)\s+(?:shows|indicates|finds)',  # Research claims
            r'\b(?:million|billion|trillion)\b',  # Large numbers
        ]
        
        if any(re.search(pattern, sentence, re.IGNORECASE) for pattern in high_risk_patterns):
            return "high"
        
        # Medium-risk indicators
        medium_risk_patterns = [
            r'\d{4}',  # Years
            r'\b(?:is|are|was|were)\s+\d+',  # Numerical statements
        ]
        
        if any(re.search(pattern, sentence, re.IGNORECASE) for pattern in medium_risk_patterns):
            return "medium"
        
        return "low"

    async def _extract_claims_llm(self, response: str, max_claims: int) -> list[Claim]:
        """Extract claims using LLM.
        
        Args:
            response: Response text
            max_claims: Maximum claims to extract
            
        Returns:
            List of Claim objects
        """
        if not self.ai_service:
            return self._extract_claims_rule_based(response, max_claims)
        
        try:
            prompt = f"""Extract atomic factual claims from the following text. 
Return ONLY a JSON array of claims, each with: id, claim, claim_type (date|number|entity|general), original_span, risk (low|medium|high).

Text: {response[:2000]}

Return JSON format:
[
  {{
    "id": "c1",
    "claim": "...",
    "claim_type": "date|number|entity|general",
    "original_span": "...",
    "risk": "low|medium|high"
  }}
]

Return ONLY valid JSON, no additional text."""
            
            # Use a default platform if available, otherwise fall back to rule-based
            try:
                llm_response = await self.ai_service.get_response(
                    "openai", prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                # Extract JSON from response
                json_match = re.search(r'\[.*?\]', llm_response, re.DOTALL)
                if json_match:
                    claims_data = json.loads(json_match.group(0))
                    claims = []
                    for idx, claim_data in enumerate(claims_data[:max_claims], 1):
                        claims.append(Claim(
                            id=claim_data.get("id", f"c{idx}"),
                            claim=claim_data.get("claim", ""),
                            claim_type=claim_data.get("claim_type", "general"),
                            original_span=claim_data.get("original_span", ""),
                            risk=claim_data.get("risk", "low")
                        ))
                    return claims
            except Exception as e:
                logger.warning("llm_claim_extraction_failed", error=str(e))
                # Fall back to rule-based
        
        except Exception as e:
            logger.error("claim_extraction_error", error=str(e))
        
        # Fallback to rule-based
        return self._extract_claims_rule_based(response, max_claims)


class EvidenceRetriever:
    """Retrieves evidence from web search using SerpAPI."""

    def __init__(self, api_key: str | None, timeout: int = 10, top_k: int = 5):
        """Initialize evidence retriever.
        
        Args:
            api_key: SerpAPI API key
            timeout: Request timeout in seconds
            top_k: Number of top results to retrieve
        """
        self.api_key = api_key
        self.timeout = timeout
        self.top_k = top_k
        self._cache: dict[str, tuple[list[Evidence], float]] = {}
        self._cache_ttl = 3600  # 1 hour

    async def retrieve_evidence(self, claim: str) -> list[Evidence]:
        """Retrieve evidence for a claim.
        
        Args:
            claim: Claim text to search for
            
        Returns:
            List of Evidence objects
        """
        if not self.api_key:
            logger.warning("serpapi_key_missing", claim=claim[:50])
            return []
        
        # Check cache
        cache_key = claim.lower().strip()
        if cache_key in self._cache:
            cached_results, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return cached_results
        
        try:
            # Use SerpAPI Google search
            params = {
                "q": claim,
                "api_key": self.api_key,
                "num": self.top_k,
            }
            
            timeout_config = httpx.Timeout(self.timeout, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout_config, follow_redirects=True) as client:
                response = await client.get(
                    "https://serpapi.com/search",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                
                evidence_list = []
                organic_results = data.get("organic_results", [])
                
                for idx, result in enumerate(organic_results[:self.top_k], 1):
                    url = result.get("link", "")
                    title = result.get("title", "")
                    snippet = result.get("snippet", "")
                    domain = urlparse(url).netloc if url else ""
                    
                    evidence_list.append(Evidence(
                        url=url,
                        title=title,
                        snippet=snippet,
                        source_rank=idx,
                        domain=domain,
                    ))
                
                # Filter duplicates and low-quality domains
                evidence_list = self._filter_evidence(evidence_list)
                
                # Cache results
                self._cache[cache_key] = (evidence_list, time.time())
                
                return evidence_list
                
        except httpx.TimeoutException:
            logger.warning("serpapi_timeout", claim=claim[:50])
            return []
        except httpx.HTTPStatusError as e:
            logger.error("serpapi_http_error", status=e.response.status_code, claim=claim[:50])
            return []
        except Exception as e:
            logger.error("serpapi_error", error=str(e), claim=claim[:50])
            return []

    def _filter_evidence(self, evidence_list: list[Evidence]) -> list[Evidence]:
        """Filter evidence to remove duplicates and low-quality sources.
        
        Args:
            evidence_list: List of evidence to filter
            
        Returns:
            Filtered list of evidence
        """
        # Remove duplicates by URL
        seen_urls = set()
        filtered = []
        
        for evidence in evidence_list:
            if evidence.url and evidence.url not in seen_urls:
                seen_urls.add(evidence.url)
                # Basic domain filtering (can be enhanced with whitelist/blacklist)
                if self._is_reputable_domain(evidence.domain):
                    filtered.append(evidence)
        
        return filtered

    def _is_reputable_domain(self, domain: str) -> bool:
        """Check if domain is reputable (basic implementation).
        
        Args:
            domain: Domain to check
            
        Returns:
            True if domain appears reputable
        """
        if not domain:
            return False
        
        # Basic blacklist
        blacklist = [
            "spam.com",
            "fake-news.com",
        ]
        
        if any(blacklisted in domain.lower() for blacklisted in blacklist):
            return False
        
        # Prefer common reputable domains (can be enhanced with whitelist)
        reputable_indicators = [
            ".edu",
            ".gov",
            ".org",
            "wikipedia.org",
            "bbc.com",
            "reuters.com",
            "ap.org",
        ]
        
        # Don't filter out, just prefer - return True for all non-blacklisted
        return True


class EvidenceTextFetcher:
    """Fetches full text content from evidence URLs."""

    def __init__(self, timeout: int = 10, max_text_length: int = 4000):
        """Initialize evidence text fetcher.
        
        Args:
            timeout: HTTP request timeout in seconds
            max_text_length: Maximum text length to extract per source
        """
        self.timeout = timeout
        self.max_text_length = max_text_length

    async def fetch_text(self, evidence: Evidence) -> str:
        """Fetch full text from evidence URL.
        
        Args:
            evidence: Evidence object with URL
            
        Returns:
            Extracted text (or snippet if fetching fails)
        """
        if not evidence.url:
            return evidence.snippet
        
        try:
            # Try to use trafilatura if available
            try:
                import trafilatura
                
                timeout_config = httpx.Timeout(self.timeout, connect=5.0)
                async with httpx.AsyncClient(timeout=timeout_config, follow_redirects=True) as client:
                    response = await client.get(evidence.url)
                    response.raise_for_status()
                    html_content = response.text
                    
                    extracted_text = trafilatura.extract(html_content)
                    if extracted_text:
                        # Limit text length
                        return extracted_text[:self.max_text_length]
            except ImportError:
                # trafilatura not available, use snippet
                pass
            except Exception as e:
                logger.warning("text_extraction_failed", url=evidence.url, error=str(e))
        
        except Exception as e:
            logger.warning("url_fetch_failed", url=evidence.url, error=str(e))
        
        # Fallback to snippet
        return evidence.snippet


class ClaimVerifier:
    """Verifies claims against evidence using LLM judge."""

    def __init__(
        self,
        ai_service: AIPlatformService,
        judge_platform_id: str,
        timeout: int = 30,
    ):
        """Initialize claim verifier.
        
        Args:
            ai_service: AI service for LLM verification
            judge_platform_id: Platform ID for judge LLM
            timeout: Verification timeout in seconds
        """
        self.ai_service = ai_service
        self.judge_platform_id = judge_platform_id
        self.timeout = timeout

    async def verify_claim(
        self,
        claim: Claim,
        evidence_list: list[Evidence],
        text_fetcher: EvidenceTextFetcher,
    ) -> dict[str, Any]:
        """Verify a claim against evidence.
        
        Args:
            claim: Claim to verify
            evidence_list: List of evidence to check against
            text_fetcher: Text fetcher for getting full content
            
        Returns:
            Verification result with verdict, confidence, and top evidence
        """
        if not evidence_list:
            return {
                "verdict": "NOT_ENOUGH_INFO",
                "confidence": 0.0,
                "top_evidence": [],
            }
        
        # Fetch text for top evidence
        evidence_with_text = []
        for evidence in evidence_list[:3]:  # Check top 3 evidence
            text = await text_fetcher.fetch_text(evidence)
            evidence_with_text.append((evidence, text))
        
        # Verify against each evidence
        verification_results = []
        for evidence, text in evidence_with_text:
            try:
                result = await asyncio.wait_for(
                    self._verify_with_llm(claim.claim, text, evidence),
                    timeout=self.timeout,
                )
                verification_results.append(result)
            except asyncio.TimeoutError:
                logger.warning("verification_timeout", claim_id=claim.id)
                continue
            except Exception as e:
                logger.warning("verification_error", claim_id=claim.id, error=str(e))
                continue
        
        # Aggregate results
        return self._aggregate_verification_results(verification_results, evidence_list)

    async def _verify_with_llm(
        self,
        claim: str,
        evidence_text: str,
        evidence: Evidence,
    ) -> dict[str, Any]:
        """Verify claim using LLM.
        
        Args:
            claim: Claim text
            evidence_text: Evidence text
            evidence: Evidence object
            
        Returns:
            Verification result
        """
        prompt = f"""Verify if the following claim is supported, refuted, or there is not enough information in the evidence.

Claim: {claim}

Evidence:
{evidence_text[:3000]}

Analyze whether the claim is:
- SUPPORTED: The evidence clearly supports the claim
- REFUTED: The evidence contradicts or refutes the claim
- NOT_ENOUGH_INFO: The evidence doesn't contain enough information to determine

Return ONLY JSON:
{{
    "verdict": "SUPPORTED|REFUTED|NOT_ENOUGH_INFO",
    "confidence": 0.0-1.0,
    "explanation": "brief explanation"
}}"""
        
        try:
            response = await self.ai_service.get_response(
                self.judge_platform_id,
                prompt,
                system_prompt=JUDGE_SYSTEM_PROMPT,
            )
            
            # Extract JSON
            json_match = re.search(r'\{.*?"verdict".*?"confidence".*?\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return {
                    "verdict": result.get("verdict", "NOT_ENOUGH_INFO"),
                    "confidence": float(result.get("confidence", 0.0)),
                    "explanation": result.get("explanation", ""),
                    "evidence": evidence,
                }
        except Exception as e:
            logger.warning("llm_verification_failed", error=str(e))
        
        return {
            "verdict": "NOT_ENOUGH_INFO",
            "confidence": 0.0,
            "explanation": "Verification failed",
            "evidence": evidence,
        }

    def _aggregate_verification_results(
        self,
        verification_results: list[dict[str, Any]],
        evidence_list: list[Evidence],
    ) -> dict[str, Any]:
        """Aggregate verification results from multiple evidence.
        
        Args:
            verification_results: List of verification results
            evidence_list: Original evidence list
            
        Returns:
            Aggregated result with final verdict
        """
        if not verification_results:
            return {
                "verdict": "NOT_ENOUGH_INFO",
                "confidence": 0.0,
                "top_evidence": [],
            }
        
        # Count verdicts
        supported = [r for r in verification_results if r["verdict"] == "SUPPORTED"]
        refuted = [r for r in verification_results if r["verdict"] == "REFUTED"]
        not_enough = [r for r in verification_results if r["verdict"] == "NOT_ENOUGH_INFO"]
        
        # Get best confidence scores
        best_support = max([r["confidence"] for r in supported], default=0.0)
        best_refute = max([r["confidence"] for r in refuted], default=0.0)
        
        # Decision logic
        threshold_support = 0.6
        threshold_refute = 0.6
        
        if best_refute >= threshold_refute and best_refute > best_support + 0.1:
            verdict = "REFUTED"
            confidence = best_refute
            top_evidence = [r["evidence"] for r in refuted if r["confidence"] == best_refute]
        elif best_support >= threshold_support:
            verdict = "SUPPORTED"
            confidence = best_support
            top_evidence = [r["evidence"] for r in supported if r["confidence"] == best_support]
        else:
            verdict = "NOT_ENOUGH_INFO"
            confidence = max(best_support, best_refute, 0.3)
            top_evidence = evidence_list[:1] if evidence_list else []
        
        return {
            "verdict": verdict,
            "confidence": confidence,
            "top_evidence": top_evidence[:3],  # Top 3 evidence
        }


class ExternalFactCheckScorer:
    """Orchestrates external fact checking and computes sub-score."""

    def __init__(
        self,
        ai_service: AIPlatformService,
        judge_platform_id: str,
    ):
        """Initialize external fact check scorer.
        
        Args:
            ai_service: AI service for LLM operations
            judge_platform_id: Platform ID for judge LLM
        """
        self.ai_service = ai_service
        self.judge_platform_id = judge_platform_id
        settings = get_settings().external_fact_check
        
        self.claim_extractor = ClaimExtractor(
            use_llm=settings.claim_extraction_use_llm,
            ai_service=ai_service if settings.claim_extraction_use_llm else None,
        )
        self.evidence_retriever = EvidenceRetriever(
            api_key=settings.serpapi_api_key,
            timeout=settings.search_timeout,
            top_k=settings.top_k_results,
        )
        self.text_fetcher = EvidenceTextFetcher(timeout=settings.search_timeout)
        self.claim_verifier = ClaimVerifier(
            ai_service=ai_service,
            judge_platform_id=judge_platform_id,
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
        
        # Step 1: Extract claims
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
        
        # Step 2: Retrieve evidence for each claim (with concurrency control)
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent searches
        
        async def retrieve_for_claim(claim: Claim) -> tuple[Claim, list[Evidence]]:
            async with semaphore:
                evidence = await self.evidence_retriever.retrieve_evidence(claim.claim)
                return (claim, evidence)
        
        claim_evidence_pairs = await asyncio.gather(
            *[retrieve_for_claim(claim) for claim in claims],
            return_exceptions=True,
        )
        
        # Step 3: Verify claims against evidence
        verified_claims = []
        all_sources = set()
        
        for pair in claim_evidence_pairs:
            if isinstance(pair, Exception):
                logger.error("evidence_retrieval_error", error=str(pair))
                continue
            
            claim, evidence_list = pair
            all_sources.update(e.url for e in evidence_list if e.url)
            
            # Verify claim
            verification = await self.claim_verifier.verify_claim(
                claim,
                evidence_list,
                self.text_fetcher,
            )
            
            # Convert to schema format
            top_evidence_schema = [
                ExternalFactCheckEvidence(
                    url=e.url,
                    title=e.title,
                    snippet=e.snippet,
                    source_rank=e.source_rank,
                    domain=e.domain,
                )
                for e in verification["top_evidence"]
            ]
            
            verified_claims.append(ExternalFactCheckClaim(
                id=claim.id,
                claim=claim.claim,
                claim_type=claim.claim_type,
                original_span=claim.original_span,
                risk=claim.risk,
                verdict=verification["verdict"],
                confidence=verification["confidence"],
                top_evidence=top_evidence_schema,
            ))
        
        # Step 4: Calculate sub-score
        score, coverage = self._calculate_score(verified_claims)
        
        return ExternalFactCheckResult(
            sub_score_name="External Fact Check",
            score=score,
            coverage=coverage,
            claims=verified_claims,
            sources_used=list(all_sources),
            notes=[],
        )

    def _calculate_score(
        self,
        verified_claims: list[ExternalFactCheckClaim],
    ) -> tuple[int, float]:
        """Calculate sub-score from verified claims.
        
        Args:
            verified_claims: List of verified claims
            
        Returns:
            Tuple of (score 0-100, coverage 0-1)
        """
        if not verified_claims:
            return (50, 0.0)
        
        # Calculate net score
        net_score = 0.0
        claims_with_evidence = 0
        
        for claim in verified_claims:
            if claim.verdict != "NOT_ENOUGH_INFO":
                claims_with_evidence += 1
            
            if claim.verdict == "SUPPORTED":
                weight = 1.5 if claim.risk == "high" else 1.0
                net_score += weight
            elif claim.verdict == "REFUTED":
                weight = -1.5 if claim.risk == "high" else -1.0
                net_score += weight
            # NOT_ENOUGH_INFO contributes 0
        
        # Normalize to 0-100
        # Base score is 50 (neutral), adjust based on net_score
        max_possible = len(verified_claims) * 1.5  # Assuming all high-risk
        if max_possible > 0:
            normalized = (net_score / max_possible) * 50  # Scale to ±50 from center
            score = int(50 + normalized)
            score = max(0, min(100, score))  # Clamp to 0-100
        else:
            score = 50
        
        # Calculate coverage
        coverage = claims_with_evidence / len(verified_claims) if verified_claims else 0.0
        
        return (score, coverage)
