"""Service for extracting and verifying citations from LLM responses."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Union
from urllib.parse import urlparse

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Citation:
    """Represents a citation found in text."""
    
    url: str
    text: str  # The text that mentions/cites this URL
    position: int  # Character position in original text
    context: str  # Surrounding text context


@dataclass
class CitationVerificationResult:
    """Result of verifying a citation."""
    
    citation: Citation
    is_valid: bool  # URL is accessible
    is_accessible: bool  # URL can be fetched
    status_code: Optional[int] = None
    content_preview: Optional[str] = None  # First 500 chars of content
    full_content: Optional[str] = None  # Full page content for claim verification
    error: Optional[str] = None


class CitationVerifier:
    """Service for extracting and verifying citations from text."""
    
    def __init__(self, timeout: int = 10):
        """Initialize citation verifier.
        
        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AI-Audit/1.0; Citation-Verifier)"
                }
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def extract_citations(self, text: str) -> list[Citation]:
        """Extract all citations (URLs) from text.
        
        Args:
            text: The text to extract citations from
            
        Returns:
            List of Citation objects found in the text
        """
        citations = []
        
        # Pattern 1: Full URLs (http://, https://, www.)
        url_patterns = [
            r'https?://[^\s\)\]\>]+',  # http:// or https:// URLs
            r'www\.[^\s\)\]\>]+',  # www. URLs
        ]
        
        for pattern in url_patterns:
            for match in re.finditer(pattern, text):
                url = match.group(0).rstrip('.,;:!?)')
                # Clean up common trailing characters
                url = url.rstrip('.,;:!?)')
                
                # Validate URL format
                if self._is_valid_url(url):
                    # Get context (50 chars before and after)
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]
                    
                    citations.append(Citation(
                        url=url,
                        text=text[max(0, match.start()-20):match.end()+20],
                        position=match.start(),
                        context=context
                    ))
        
        # Pattern 2: Markdown links [text](url)
        markdown_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        for match in re.finditer(markdown_pattern, text):
            link_text = match.group(1)
            url = match.group(2)
            
            if self._is_valid_url(url):
                citations.append(Citation(
                    url=url,
                    text=link_text,
                    position=match.start(),
                    context=text[max(0, match.start()-50):match.end()+50]
                ))
        
        # Pattern 3: DOI references
        doi_pattern = r'doi[:\s]+(10\.\d+/[^\s\)]+)'
        for match in re.finditer(doi_pattern, text, re.IGNORECASE):
            doi = match.group(1)
            url = f"https://doi.org/{doi}"
            citations.append(Citation(
                url=url,
                text=f"DOI: {doi}",
                position=match.start(),
                context=text[max(0, match.start()-50):match.end()+50]
            ))
        
        # Remove duplicates (same URL)
        seen_urls = set()
        unique_citations = []
        for citation in citations:
            normalized_url = self._normalize_url(citation.url)
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_citations.append(citation)
        
        return unique_citations
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid format."""
        try:
            # Add protocol if missing
            if not url.startswith(('http://', 'https://')):
                if url.startswith('www.'):
                    url = 'https://' + url
                else:
                    return False
            
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            if url.startswith('www.'):
                url = 'https://' + url
            else:
                return url
        
        # Remove trailing slashes and fragments
        url = url.rstrip('/')
        if '#' in url:
            url = url.split('#')[0]
        
        return url.lower()
    
    async def verify_citation(self, citation: Citation) -> CitationVerificationResult:
        """Verify if a citation URL is accessible and valid.
        
        Args:
            citation: Citation object to verify
            
        Returns:
            CitationVerificationResult with verification details
        """
        url = citation.url
        
        # Normalize URL
        if not url.startswith(('http://', 'https://')):
            if url.startswith('www.'):
                url = 'https://' + url
            else:
                return CitationVerificationResult(
                    citation=citation,
                    is_valid=False,
                    is_accessible=False,
                    error="Invalid URL format"
                )
        
        client = self._get_client()
        
        try:
            # Make HEAD request first (faster, checks if accessible)
            try:
                response = await client.head(url, follow_redirects=True)
                status_code = response.status_code
                is_accessible = 200 <= status_code < 400
            except Exception:
                # If HEAD fails, try GET
                try:
                    response = await client.get(url, follow_redirects=True)
                    status_code = response.status_code
                    is_accessible = 200 <= status_code < 400
                except Exception as e:
                    return CitationVerificationResult(
                        citation=citation,
                        is_valid=False,
                        is_accessible=False,
                        error=str(e)
                    )
            
            # Fetch full content if accessible for claim verification
            content_preview = None
            full_content = None
            if is_accessible and status_code == 200:
                try:
                    # Fetch full content
                    get_response = await client.get(url)
                    content_type = get_response.headers.get('content-type', '').lower()
                    
                    if 'text/html' in content_type or 'text/plain' in content_type:
                        # Extract text content (remove HTML tags)
                        raw_content = get_response.text
                        
                        # Remove HTML tags and clean up whitespace
                        text_content = re.sub(r'<[^>]+>', ' ', raw_content)
                        text_content = re.sub(r'\s+', ' ', text_content)  # Normalize whitespace
                        text_content = text_content.strip()
                        
                        # Store full content for claim verification (limit to 50KB for performance)
                        full_content = text_content[:50000] if len(text_content) > 50000 else text_content
                        
                        # Store preview (first 500 chars)
                        content_preview = full_content[:500] if full_content else None
                except Exception as e:
                    logger.warning("Failed to fetch citation content", url=url, error=str(e))
                    # Content fetch is optional, continue with verification
            
            return CitationVerificationResult(
                citation=citation,
                is_valid=True,
                is_accessible=is_accessible,
                status_code=status_code,
                content_preview=content_preview,
                full_content=full_content
            )
            
        except httpx.TimeoutException:
            return CitationVerificationResult(
                citation=citation,
                is_valid=True,
                is_accessible=False,
                error="Request timeout"
            )
        except Exception as e:
            return CitationVerificationResult(
                citation=citation,
                is_valid=True,
                is_accessible=False,
                error=str(e)
            )
    
    async def verify_all_citations(self, text: str) -> list[CitationVerificationResult]:
        """Extract and verify all citations in text.
        
        Args:
            text: Text to extract and verify citations from
            
        Returns:
            List of CitationVerificationResult for each citation found
        """
        citations = self.extract_citations(text)
        
        if not citations:
            return []
        
        # Verify all citations concurrently
        import asyncio
        verification_tasks = [self.verify_citation(citation) for citation in citations]
        results = await asyncio.gather(*verification_tasks, return_exceptions=True)
        
        # Filter out exceptions and return valid results
        verified_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("Citation verification error", error=str(result))
            else:
                verified_results.append(result)
        
        return verified_results
    
    def get_citation_statistics(self, verification_results: list[CitationVerificationResult]) -> dict:
        """Get statistics about citation verification.
        
        Args:
            verification_results: List of verification results
            
        Returns:
            Dictionary with statistics
        """
        if not verification_results:
            return {
                'total': 0,
                'valid': 0,
                'accessible': 0,
                'invalid': 0,
                'accessibility_rate': 0.0,
                'with_content': 0
            }
        
        total = len(verification_results)
        valid = sum(1 for r in verification_results if r.is_valid)
        accessible = sum(1 for r in verification_results if r.is_accessible)
        invalid = total - valid
        with_content = sum(1 for r in verification_results if r.full_content is not None)
        
        return {
            'total': total,
            'valid': valid,
            'accessible': accessible,
            'invalid': invalid,
            'accessibility_rate': accessible / total if total > 0 else 0.0,
            'with_content': with_content,
            'content_rate': with_content / total if total > 0 else 0.0
        }

    async def verify_claim_source_alignment(
        self, 
        claim: str, 
        verification_result: CitationVerificationResult,
        use_llm: bool = False,
        ai_service = None,
        judge_platform_id: Optional[str] = None
    ) -> dict:
        """Verify if a claim in the response matches the content on the cited page.
        
        Args:
            claim: The factual claim from the response to verify
            verification_result: Citation verification result with page content
            use_llm: Whether to use LLM for semantic verification (default: False)
            ai_service: AI service for LLM verification (required if use_llm=True)
            judge_platform_id: Platform ID for LLM (required if use_llm=True)
            
        Returns:
            Dictionary with:
            - verified: bool - Whether claim is verified in source
            - confidence: float - Confidence score (0.0-1.0)
            - method: str - Verification method used
            - explanation: str - Brief explanation
        """
        if not verification_result.is_accessible or not verification_result.full_content:
            return {
                'verified': False,
                'confidence': 0.0,
                'method': 'no_content',
                'explanation': 'Citation not accessible or content not available'
            }
        
        source_content = verification_result.full_content.lower()
        claim_lower = claim.lower()
        
        # Method 1: Exact phrase matching (highest confidence)
        if claim_lower in source_content:
            return {
                'verified': True,
                'confidence': 1.0,
                'method': 'exact_match',
                'explanation': 'Claim found verbatim in source'
            }
        
        # Method 2: Key phrase matching (extract key phrases from claim)
        key_phrases = self._extract_key_phrases(claim)
        matched_phrases = sum(1 for phrase in key_phrases if phrase in source_content)
        phrase_match_ratio = matched_phrases / len(key_phrases) if key_phrases else 0
        
        if phrase_match_ratio >= 0.7:
            return {
                'verified': True,
                'confidence': 0.8,
                'method': 'key_phrase_match',
                'explanation': f'{matched_phrases}/{len(key_phrases)} key phrases found in source'
            }
        
        # Method 3: Semantic similarity (if LLM available)
        if use_llm and ai_service and judge_platform_id:
            try:
                return await self._verify_with_llm(
                    claim, source_content, ai_service, judge_platform_id
                )
            except Exception as e:
                logger.warning("LLM verification failed", error=str(e))
        
        # Method 4: Partial word overlap (lower confidence)
        claim_words = set(claim_lower.split())
        source_words = set(source_content.split())
        common_words = claim_words & source_words
        
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their'}
        meaningful_common = common_words - stop_words
        
        if len(meaningful_common) >= 3:
            overlap_ratio = len(meaningful_common) / max(len(claim_words - stop_words), 1)
            if overlap_ratio >= 0.5:
                return {
                    'verified': True,
                    'confidence': 0.6,
                    'method': 'word_overlap',
                    'explanation': f'Significant word overlap ({len(meaningful_common)} words)'
                }
        
        # No verification found
        return {
            'verified': False,
            'confidence': 0.0,
            'method': 'no_match',
            'explanation': 'Claim not found in source content'
        }

    def _extract_key_phrases(self, text: str) -> list[str]:
        """Extract key phrases from text for matching.
        
        Args:
            text: Text to extract phrases from
            
        Returns:
            List of key phrases (3-5 word sequences)
        """
        words = text.lower().split()
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their'}
        
        # Extract meaningful phrases (3-5 words, excluding stop words)
        phrases = []
        for i in range(len(words) - 2):
            phrase_words = words[i:i+3]
            if len([w for w in phrase_words if w not in stop_words]) >= 2:
                phrases.append(' '.join(phrase_words))
        
        # Also extract longer phrases (4-5 words)
        for i in range(len(words) - 3):
            phrase_words = words[i:i+4]
            if len([w for w in phrase_words if w not in stop_words]) >= 3:
                phrases.append(' '.join(phrase_words))
        
        # Return unique phrases, sorted by length (longer first)
        return sorted(set(phrases), key=len, reverse=True)[:10]  # Top 10 phrases

    async def _verify_with_llm(
        self, 
        claim: str, 
        source_content: str,
        ai_service,
        judge_platform_id: str
    ) -> dict:
        """Verify claim using LLM semantic analysis.
        
        Args:
            claim: Claim to verify
            source_content: Source page content (truncated to 5000 chars for efficiency)
            ai_service: AI service for LLM
            judge_platform_id: Platform ID for LLM
            
        Returns:
            Verification result dictionary
        """
        # Truncate source content for LLM (keep first 5000 chars)
        truncated_source = source_content[:5000]
        
        prompt = f"""Verify if the following claim is supported by the source content.

Claim: {claim}

Source Content (from cited page):
{truncated_source}

Analyze whether the claim accurately represents information found in the source.
Consider:
1. Is the claim directly stated in the source?
2. Is the claim a reasonable inference from the source?
3. Does the claim contradict the source?
4. Is the claim not mentioned in the source?

Return ONLY JSON: {{
    "verified": <true|false>,
    "confidence": <0.0-1.0>,
    "explanation": "<brief explanation>"
}}"""
        
        from app.services.comparison.utils import JUDGE_SYSTEM_PROMPT
        if not judge_platform_id:
            raise ValueError("judge_platform_id is required for LLM verification")
        judge_response = await ai_service.get_response(
            judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
        )
        
        # Parse JSON response (simplified - in production use proper JSON parsing)
        import json
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', judge_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return {
                    'verified': result.get('verified', False),
                    'confidence': float(result.get('confidence', 0.0)),
                    'method': 'llm_semantic',
                    'explanation': result.get('explanation', 'LLM verification')
                }
        except Exception:
            pass
        
        # Fallback
        return {
            'verified': False,
            'confidence': 0.0,
            'method': 'llm_failed',
            'explanation': 'LLM verification failed'
        }

