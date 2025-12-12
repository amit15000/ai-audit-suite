"""Service for extracting and verifying citations from LLM responses."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
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
                response = await client.head(url, allow_redirects=True)
                status_code = response.status_code
                is_accessible = 200 <= status_code < 400
            except Exception:
                # If HEAD fails, try GET
                try:
                    response = await client.get(url, allow_redirects=True)
                    status_code = response.status_code
                    is_accessible = 200 <= status_code < 400
                except Exception as e:
                    return CitationVerificationResult(
                        citation=citation,
                        is_valid=False,
                        is_accessible=False,
                        error=str(e)
                    )
            
            # Get content preview if accessible
            content_preview = None
            if is_accessible and response.status_code == 200:
                try:
                    # Only fetch text content
                    content_type = response.headers.get('content-type', '').lower()
                    if 'text/html' in content_type or 'text/plain' in content_type:
                        # Fetch full content for preview
                        get_response = await client.get(url)
                        content = get_response.text[:1000]  # First 1000 chars
                        # Extract text (remove HTML tags roughly)
                        content = re.sub(r'<[^>]+>', '', content)
                        content_preview = content[:500]  # First 500 chars
                except Exception:
                    pass  # Content preview is optional
            
            return CitationVerificationResult(
                citation=citation,
                is_valid=True,
                is_accessible=is_accessible,
                status_code=status_code,
                content_preview=content_preview
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
                'accessibility_rate': 0.0
            }
        
        total = len(verification_results)
        valid = sum(1 for r in verification_results if r.is_valid)
        accessible = sum(1 for r in verification_results if r.is_accessible)
        invalid = total - valid
        
        return {
            'total': total,
            'valid': valid,
            'accessible': accessible,
            'invalid': invalid,
            'accessibility_rate': accessible / total if total > 0 else 0.0
        }

