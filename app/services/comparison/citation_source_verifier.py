"""Service for verifying citations across multiple academic and legal sources."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import httpx
import structlog

from app.services.comparison.citation_enricher import EnrichedCitation
from app.services.comparison.citation_openai_verifier import CitationOpenAIVerifier, OpenAIVerificationResult
from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


@dataclass
class SourceVerificationResult:
    """Result of verifying a citation in a specific source."""
    
    source_name: str  # 'google_scholar', 'pubmed', 'doi', 'courtlistener', 'web'
    verified: bool
    source_url: Optional[str] = None  # Complete link to the verified source
    confidence: float = 0.0  # 0.0-1.0 confidence in verification
    error: Optional[str] = None
    metadata: Optional[dict] = None  # Additional metadata from source


@dataclass
class CitationVerificationReport:
    """Complete verification report for a citation."""
    
    original_citation: str
    enriched: EnrichedCitation
    verified: bool  # True if verified in at least one source
    verification_results: list[SourceVerificationResult]
    verified_source_url: Optional[str] = None  # Best verified source URL
    confidence: float = 0.0  # Overall confidence (0.0-1.0)


class CitationSourceVerifier:
    """Service for verifying citations across multiple sources."""
    
    def __init__(self, timeout: int = 10, ai_service: Optional[AIPlatformService] = None, use_openai: bool = True):
        """Initialize citation source verifier.
        
        Args:
            timeout: HTTP request timeout in seconds
            ai_service: AI service for OpenAI verification (optional)
            use_openai: Whether to use OpenAI for intelligent verification (default: True)
        """
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self.use_openai = use_openai
        self.openai_verifier: Optional[CitationOpenAIVerifier] = None
        if use_openai and ai_service:
            self.openai_verifier = CitationOpenAIVerifier(ai_service)
    
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
    
    def _verify_paper_exists(self, response_text: str, citation: EnrichedCitation) -> bool:
        """Check if the page actually contains a real paper/resource.
        
        Args:
            response_text: HTML/text content of the page
            citation: Enriched citation with metadata
            
        Returns:
            True if paper appears to exist, False otherwise
        """
        text_lower = response_text.lower()
        
        # Negative indicators - page says no results/not found
        negative_indicators = [
            'no results found',
            'no results',
            'produced no results',
            'not found',
            '404',
            'page not found',
            'article not found',
            'paper not found',
            'document not found',
            'does not exist',
            'could not be found',
            'sorry, your query',
            'no matching',
            'no papers found',
            'no articles found'
        ]
        
        # Check for negative indicators
        for indicator in negative_indicators:
            if indicator in text_lower:
                return False
        
        # Positive indicators - page contains actual paper/resource
        positive_indicators = [
            'abstract',
            'doi:',
            'published',
            'authors',
            'citation',
            'references',
            'full text',
            'pdf',
            'download',
            'article',
            'paper',
            'research',
            'study',
            'journal',
            'volume',
            'issue',
            'pages',
            'peer reviewed'
        ]
        
        # Count positive indicators
        positive_count = sum(1 for indicator in positive_indicators if indicator in text_lower)
        
        # If we have multiple positive indicators, it's likely a real paper
        if positive_count >= 3:
            return True
        
        # If we have title match, it's more likely real
        if citation.title:
            title_words = citation.title.lower().split()[:5]  # First 5 words
            title_match_count = sum(1 for word in title_words if len(word) > 3 and word in text_lower)
            if title_match_count >= 2:
                return True
        
        # If we have DOI in the page, it's likely real
        if citation.doi and citation.doi.lower() in text_lower:
            return True
        
        # Default: if no negative indicators and some content, assume it exists
        # But be conservative - require at least one positive indicator
        return positive_count >= 1
    
    async def verify_doi(self, doi: str) -> SourceVerificationResult:
        """Verify citation via DOI and check if paper actually exists.
        
        Args:
            doi: DOI string (e.g., "10.1234/example")
            
        Returns:
            SourceVerificationResult
        """
        try:
            # Normalize DOI
            doi = doi.strip()
            if not doi.startswith('10.'):
                return SourceVerificationResult(
                    source_name='doi',
                    verified=False,
                    error="Invalid DOI format"
                )
            
            # Remove 'doi:' prefix if present
            doi = re.sub(r'^doi:?\s*', '', doi, flags=re.IGNORECASE)
            
            # DOI resolver URL
            doi_url = f"https://doi.org/{doi}"
            
            client = self._get_client()
            response = await client.get(doi_url, follow_redirects=True)
            
            if response.status_code == 200:
                final_url = str(response.url)
                response_text = response.text
                
                # Create a minimal citation object for verification
                from app.services.comparison.citation_enricher import EnrichedCitation
                citation_check = EnrichedCitation(original_url=doi_url, doi=doi)
                
                # Actually check if paper exists on the page
                paper_exists = self._verify_paper_exists(response_text, citation_check)
                
                if paper_exists:
                    return SourceVerificationResult(
                        source_name='doi',
                        verified=True,
                        source_url=final_url,
                        confidence=0.9,
                        metadata={'doi': doi, 'resolved_url': final_url}
                    )
                else:
                    return SourceVerificationResult(
                        source_name='doi',
                        verified=False,
                        error="DOI resolves but page indicates no paper found"
                    )
            else:
                return SourceVerificationResult(
                    source_name='doi',
                    verified=False,
                    error=f"DOI not found (status: {response.status_code})"
                )
        except Exception as e:
            return SourceVerificationResult(
                source_name='doi',
                verified=False,
                error=str(e)
            )
    
    async def verify_google_scholar(self, citation: EnrichedCitation) -> SourceVerificationResult:
        """Verify citation via Google Scholar search.
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            # Build search query
            query_parts = []
            if citation.title:
                query_parts.append(citation.title)
            if citation.authors:
                query_parts.extend(citation.authors[:2])  # First 2 authors
            if citation.year:
                query_parts.append(str(citation.year))
            
            if not query_parts:
                return SourceVerificationResult(
                    source_name='google_scholar',
                    verified=False,
                    error="Insufficient metadata for Google Scholar search"
                )
            
            query = " ".join(query_parts)
            # Google Scholar search URL (note: this is a simplified approach)
            # In production, you might want to use Google Scholar API or scraping
            search_url = f"https://scholar.google.com/scholar?q={quote(query)}"
            
            client = self._get_client()
            response = await client.get(search_url)
            
            if response.status_code == 200:
                response_text = response.text
                
                # Check if page says no results
                if not self._verify_paper_exists(response_text, citation):
                    return SourceVerificationResult(
                        source_name='google_scholar',
                        verified=False,
                        error="No matching results found in Google Scholar"
                    )
                
                # Check if results contain relevant matches
                text_lower = response_text.lower()
                title_match = citation.title and citation.title.lower() in text_lower
                
                # Try to extract first result URL
                result_url = search_url
                # Look for paper links in Google Scholar results
                paper_link_match = re.search(r'href="(/scholar\?[^"]+)"', response_text)
                if paper_link_match:
                    paper_path = paper_link_match.group(1)
                    result_url = f"https://scholar.google.com{paper_path}"
                
                if title_match or len(query_parts) >= 2:
                    return SourceVerificationResult(
                        source_name='google_scholar',
                        verified=True,
                        source_url=result_url,
                        confidence=0.7 if title_match else 0.5,
                        metadata={'query': query, 'search_url': search_url}
                    )
            
            return SourceVerificationResult(
                source_name='google_scholar',
                verified=False,
                error="No matching results found"
            )
        except Exception as e:
            return SourceVerificationResult(
                source_name='google_scholar',
                verified=False,
                error=str(e)
            )
    
    async def verify_pubmed(self, citation: EnrichedCitation) -> SourceVerificationResult:
        """Verify citation via PubMed.
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            # Build PubMed search query
            query_parts = []
            if citation.doi:
                query = citation.doi
            elif citation.title:
                query = citation.title
            elif citation.authors and citation.year:
                query = f"{citation.authors[0]} {citation.year}"
            else:
                return SourceVerificationResult(
                    source_name='pubmed',
                    verified=False,
                    error="Insufficient metadata for PubMed search"
                )
            
            # PubMed search URL
            search_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={quote(query)}"
            
            client = self._get_client()
            response = await client.get(search_url)
            
            if response.status_code == 200:
                response_text = response.text
                
                # Check if page says no results
                if not self._verify_paper_exists(response_text, citation):
                    return SourceVerificationResult(
                        source_name='pubmed',
                        verified=False,
                        error="No matching results found in PubMed"
                    )
                
                # Check if results found
                text_lower = response_text.lower()
                has_results = 'results' in text_lower or 'pmid' in text_lower
                
                if has_results:
                    # Try to extract first result URL
                    pmid_match = re.search(r'pmid[:\s]+(\d+)', response_text, re.IGNORECASE)
                    if pmid_match:
                        pmid = pmid_match.group(1)
                        result_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    else:
                        result_url = search_url
                    
                    return SourceVerificationResult(
                        source_name='pubmed',
                        verified=True,
                        source_url=result_url,
                        confidence=0.8,
                        metadata={'query': query, 'search_url': search_url}
                    )
            
            return SourceVerificationResult(
                source_name='pubmed',
                verified=False,
                error="No matching results found"
            )
        except Exception as e:
            return SourceVerificationResult(
                source_name='pubmed',
                verified=False,
                error=str(e)
            )
    
    async def verify_courtlistener(self, citation: EnrichedCitation) -> SourceVerificationResult:
        """Verify citation via CourtListener.
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            # Build search query for CourtListener
            query_parts = []
            if citation.title:
                query_parts.append(citation.title)
            if citation.original_url and 'courtlistener' in citation.original_url.lower():
                # Direct CourtListener URL
                client = self._get_client()
                response = await client.get(citation.original_url)
                if response.status_code == 200:
                    return SourceVerificationResult(
                        source_name='courtlistener',
                        verified=True,
                        source_url=citation.original_url,
                        confidence=0.9,
                        metadata={'direct_url': citation.original_url}
                    )
            
            if not query_parts:
                return SourceVerificationResult(
                    source_name='courtlistener',
                    verified=False,
                    error="Insufficient metadata for CourtListener search"
                )
            
            query = " ".join(query_parts)
            # CourtListener search URL
            search_url = f"https://www.courtlistener.com/?q={quote(query)}"
            
            client = self._get_client()
            response = await client.get(search_url)
            
            if response.status_code == 200:
                # Check if results found
                text_lower = response.text.lower()
                has_results = 'results' in text_lower or 'case' in text_lower
                
                if has_results:
                    return SourceVerificationResult(
                        source_name='courtlistener',
                        verified=True,
                        source_url=search_url,
                        confidence=0.6,
                        metadata={'query': query, 'search_url': search_url}
                    )
            
            return SourceVerificationResult(
                source_name='courtlistener',
                verified=False,
                error="No matching results found"
            )
        except Exception as e:
            return SourceVerificationResult(
                source_name='courtlistener',
                verified=False,
                error=str(e)
            )
    
    async def verify_web_url(self, url: str) -> SourceVerificationResult:
        """Verify a web URL is accessible.
        
        Args:
            url: URL to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            client = self._get_client()
            response = await client.get(url, follow_redirects=True)
            
            if response.status_code == 200:
                return SourceVerificationResult(
                    source_name='web',
                    verified=True,
                    source_url=str(response.url),  # Final URL after redirects
                    confidence=0.8,
                    metadata={'status_code': response.status_code}
                )
            else:
                return SourceVerificationResult(
                    source_name='web',
                    verified=False,
                    error=f"URL not accessible (status: {response.status_code})"
                )
        except Exception as e:
            return SourceVerificationResult(
                source_name='web',
                verified=False,
                error=str(e)
            )
    
    async def verify_via_web_search(self, citation: EnrichedCitation) -> SourceVerificationResult:
        """Verify citation via general web search (Google, Bing, etc.).
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            # Build search query
            query_parts = []
            if citation.doi:
                query = citation.doi
            elif citation.title:
                query = citation.title
            elif citation.original_url:
                query = citation.original_url
            else:
                return SourceVerificationResult(
                    source_name='web_search',
                    verified=False,
                    error="Insufficient information for web search"
                )
            
            # Try Google search (using DuckDuckGo as fallback since it doesn't require API)
            # In production, you might want to use Google Custom Search API or SerpAPI
            search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            
            client = self._get_client()
            response = await client.get(search_url)
            
            if response.status_code == 200:
                response_text = response.text
                
                # Check if page says no results
                if not self._verify_paper_exists(response_text, citation):
                    return SourceVerificationResult(
                        source_name='web_search',
                        verified=False,
                        error="No matching results found in web search"
                    )
                
                # Try to extract first result URL - but don't use search URL itself
                # Look for actual result URLs, not the search page URL
                url_patterns = [
                    r'href="(https?://(?!html\.duckduckgo\.com|duckduckgo\.com|google\.com/search)[^"]+)"',
                    r'<a[^>]+href="(https?://[^"]+)"[^>]*>',
                ]
                
                result_url = None
                for pattern in url_patterns:
                    matches = re.finditer(pattern, response_text)
                    for match in matches:
                        url = match.group(1)
                        # Skip search engine URLs, use actual content URLs
                        if not any(domain in url.lower() for domain in ['duckduckgo.com', 'google.com/search', 'bing.com/search', 'search?']):
                            result_url = url
                            break
                    if result_url:
                        break
                
                # Only verify if we found an actual source URL, not just search page
                if result_url and result_url != search_url:
                    return SourceVerificationResult(
                        source_name='web_search',
                        verified=True,
                        source_url=result_url,
                        confidence=0.6,
                        metadata={'query': query, 'search_url': search_url}
                    )
                else:
                    return SourceVerificationResult(
                        source_name='web_search',
                        verified=False,
                        error="Found search results but could not extract valid source URL"
                    )
            
            return SourceVerificationResult(
                source_name='web_search',
                verified=False,
                error="No matching results found in web search"
            )
        except Exception as e:
            return SourceVerificationResult(
                source_name='web_search',
                verified=False,
                error=str(e)
            )
    
    async def verify_via_semantic_scholar(self, citation: EnrichedCitation) -> SourceVerificationResult:
        """Verify citation via Semantic Scholar.
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            # Build search query
            query_parts = []
            if citation.doi:
                query = citation.doi
            elif citation.title:
                query = citation.title
            else:
                return SourceVerificationResult(
                    source_name='semantic_scholar',
                    verified=False,
                    error="Insufficient metadata for Semantic Scholar search"
                )
            
            # Semantic Scholar search URL
            search_url = f"https://www.semanticscholar.org/search?q={quote(query)}"
            
            client = self._get_client()
            response = await client.get(search_url)
            
            if response.status_code == 200:
                response_text = response.text
                
                # Check if page says no results
                if not self._verify_paper_exists(response_text, citation):
                    return SourceVerificationResult(
                        source_name='semantic_scholar',
                        verified=False,
                        error="No matching results found in Semantic Scholar"
                    )
                
                # Try to extract paper URL
                paper_match = re.search(r'href="(/paper/[^"]+)"', response_text)
                if paper_match:
                    paper_path = paper_match.group(1)
                    result_url = f"https://www.semanticscholar.org{paper_path}"
                else:
                    result_url = search_url
                
                return SourceVerificationResult(
                    source_name='semantic_scholar',
                    verified=True,
                    source_url=result_url,
                    confidence=0.7,
                    metadata={'query': query, 'search_url': search_url}
                )
            
            return SourceVerificationResult(
                source_name='semantic_scholar',
                verified=False,
                error="No matching results found"
            )
        except Exception as e:
            return SourceVerificationResult(
                source_name='semantic_scholar',
                verified=False,
                error=str(e)
            )
    
    async def verify_via_arxiv(self, citation: EnrichedCitation) -> SourceVerificationResult:
        """Verify citation via arXiv.
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            # Build search query
            if citation.doi:
                query = citation.doi
            elif citation.title:
                query = citation.title
            else:
                return SourceVerificationResult(
                    source_name='arxiv',
                    verified=False,
                    error="Insufficient metadata for arXiv search"
                )
            
            # arXiv search URL
            search_url = f"https://arxiv.org/search/?query={quote(query)}&searchtype=all"
            
            client = self._get_client()
            response = await client.get(search_url)
            
            if response.status_code == 200:
                response_text = response.text
                
                # Check if page says no results
                if not self._verify_paper_exists(response_text, citation):
                    return SourceVerificationResult(
                        source_name='arxiv',
                        verified=False,
                        error="No matching results found in arXiv"
                    )
                
                # Try to extract arXiv ID and URL
                arxiv_match = re.search(r'arxiv:(\d+\.\d+)', response_text, re.IGNORECASE)
                if arxiv_match:
                    arxiv_id = arxiv_match.group(1)
                    result_url = f"https://arxiv.org/abs/{arxiv_id}"
                else:
                    result_url = search_url
                
                return SourceVerificationResult(
                    source_name='arxiv',
                    verified=True,
                    source_url=result_url,
                    confidence=0.8,
                    metadata={'query': query, 'search_url': search_url}
                )
            
            return SourceVerificationResult(
                source_name='arxiv',
                verified=False,
                error="No matching results found"
            )
        except Exception as e:
            return SourceVerificationResult(
                source_name='arxiv',
                verified=False,
                error=str(e)
            )
    
    async def verify_via_crossref(self, citation: EnrichedCitation) -> SourceVerificationResult:
        """Verify citation via Crossref (DOI registry and citation database).
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            if not citation.doi:
                return SourceVerificationResult(
                    source_name='crossref',
                    verified=False,
                    error="DOI required for Crossref search"
                )
            
            # Crossref API search
            search_url = f"https://api.crossref.org/works/{citation.doi}"
            
            client = self._get_client()
            response = await client.get(search_url)
            
            if response.status_code == 200:
                data = response.json()
                # Crossref API returns 200 even for non-existent DOIs, check the message
                if 'message' in data:
                    message = data['message']
                    # Check if it's actually a valid work (has title or URL)
                    if 'title' in message or 'URL' in message:
                        result_url = message.get('URL', search_url)
                        return SourceVerificationResult(
                            source_name='crossref',
                            verified=True,
                            source_url=result_url,
                            confidence=0.9,
                            metadata={'doi': citation.doi, 'crossref_data': message}
                        )
                    else:
                        return SourceVerificationResult(
                            source_name='crossref',
                            verified=False,
                            error="DOI not found in Crossref database"
                        )
            
            return SourceVerificationResult(
                source_name='crossref',
                verified=False,
                error="DOI not found in Crossref"
            )
        except Exception as e:
            return SourceVerificationResult(
                source_name='crossref',
                verified=False,
                error=str(e)
            )
    
    async def verify_via_researchgate(self, citation: EnrichedCitation) -> SourceVerificationResult:
        """Verify citation via ResearchGate.
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            query_parts = []
            if citation.doi:
                query = citation.doi
            elif citation.title:
                query = citation.title
            else:
                return SourceVerificationResult(
                    source_name='researchgate',
                    verified=False,
                    error="Insufficient metadata for ResearchGate search"
                )
            
            search_url = f"https://www.researchgate.net/search?q={quote(query)}"
            
            client = self._get_client()
            response = await client.get(search_url)
            
            if response.status_code == 200:
                response_text = response.text
                
                # Check if page says no results
                if not self._verify_paper_exists(response_text, citation):
                    return SourceVerificationResult(
                        source_name='researchgate',
                        verified=False,
                        error="No matching results found in ResearchGate"
                    )
                
                # Try to extract publication URL
                pub_match = re.search(r'href="(/publication/[^"]+)"', response_text)
                if pub_match:
                    pub_path = pub_match.group(1)
                    result_url = f"https://www.researchgate.net{pub_path}"
                else:
                    result_url = search_url
                
                return SourceVerificationResult(
                    source_name='researchgate',
                    verified=True,
                    source_url=result_url,
                    confidence=0.7,
                    metadata={'query': query, 'search_url': search_url}
                )
            
            return SourceVerificationResult(
                source_name='researchgate',
                verified=False,
                error="No matching results found"
            )
        except Exception as e:
            return SourceVerificationResult(
                source_name='researchgate',
                verified=False,
                error=str(e)
            )
    
    async def verify_via_academia(self, citation: EnrichedCitation) -> SourceVerificationResult:
        """Verify citation via Academia.edu.
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            if citation.doi:
                query = citation.doi
            elif citation.title:
                query = citation.title
            else:
                return SourceVerificationResult(
                    source_name='academia',
                    verified=False,
                    error="Insufficient metadata for Academia.edu search"
                )
            
            search_url = f"https://www.academia.edu/search?q={quote(query)}"
            
            client = self._get_client()
            response = await client.get(search_url)
            
            if response.status_code == 200:
                response_text = response.text
                
                # Check if page says no results
                if not self._verify_paper_exists(response_text, citation):
                    return SourceVerificationResult(
                        source_name='academia',
                        verified=False,
                        error="No matching results found in Academia.edu"
                    )
                
                # Try to extract paper URL
                paper_match = re.search(r'href="(/[^"]+paper[^"]+)"', response_text)
                if paper_match:
                    paper_path = paper_match.group(1)
                    result_url = f"https://www.academia.edu{paper_path}"
                else:
                    result_url = search_url
                
                return SourceVerificationResult(
                    source_name='academia',
                    verified=True,
                    source_url=result_url,
                    confidence=0.6,
                    metadata={'query': query, 'search_url': search_url}
                )
            
            return SourceVerificationResult(
                source_name='academia',
                verified=False,
                error="No matching results found"
            )
        except Exception as e:
            return SourceVerificationResult(
                source_name='academia',
                verified=False,
                error=str(e)
            )
    
    async def verify_via_ssrn(self, citation: EnrichedCitation) -> SourceVerificationResult:
        """Verify citation via SSRN (Social Science Research Network).
        
        Args:
            citation: Enriched citation to verify
            
        Returns:
            SourceVerificationResult
        """
        try:
            if citation.doi:
                query = citation.doi
            elif citation.title:
                query = citation.title
            else:
                return SourceVerificationResult(
                    source_name='ssrn',
                    verified=False,
                    error="Insufficient metadata for SSRN search"
                )
            
            search_url = f"https://papers.ssrn.com/sol3/results.cfm?q={quote(query)}"
            
            client = self._get_client()
            response = await client.get(search_url)
            
            if response.status_code == 200:
                response_text = response.text
                
                # Check if page says no results
                if not self._verify_paper_exists(response_text, citation):
                    return SourceVerificationResult(
                        source_name='ssrn',
                        verified=False,
                        error="No matching results found in SSRN"
                    )
                
                # Try to extract paper URL
                paper_match = re.search(r'href="(/sol3/papers[^"]+)"', response_text)
                if paper_match:
                    paper_path = paper_match.group(1)
                    result_url = f"https://papers.ssrn.com{paper_path}"
                else:
                    result_url = search_url
                
                return SourceVerificationResult(
                    source_name='ssrn',
                    verified=True,
                    source_url=result_url,
                    confidence=0.7,
                    metadata={'query': query, 'search_url': search_url}
                )
            
            return SourceVerificationResult(
                source_name='ssrn',
                verified=False,
                error="No matching results found"
            )
        except Exception as e:
            return SourceVerificationResult(
                source_name='ssrn',
                verified=False,
                error=str(e)
            )
    
    async def verify_citation(
        self, 
        enriched: EnrichedCitation,
        judge_platform_id: str = "openai"
    ) -> CitationVerificationReport:
        """Verify a citation across all relevant sources globally.
        
        Uses OpenAI's web search capabilities for intelligent verification,
        which automatically searches across multiple platforms.
        
        Args:
            enriched: Enriched citation to verify
            judge_platform_id: Platform ID for OpenAI (default: "openai")
            
        Returns:
            CitationVerificationReport with all verification results
        """
        verification_results = []
        
        # First, try OpenAI verification (intelligent, searches everywhere automatically)
        if self.use_openai and self.openai_verifier:
            try:
                openai_result = await self.openai_verifier.verify_citation_with_openai(
                    enriched, judge_platform_id
                )
                
                if openai_result.verified:
                    # Convert OpenAI result to SourceVerificationResult
                    verification_results.append(
                        SourceVerificationResult(
                            source_name=openai_result.source_name or "openai_web_search",
                            verified=True,
                            source_url=openai_result.source_url,
                            confidence=openai_result.confidence,
                            metadata={
                                "explanation": openai_result.explanation,
                                "method": "openai_intelligent_search"
                            }
                        )
                    )
                    # If OpenAI verified it, we can return early (it's thorough)
                    return CitationVerificationReport(
                        original_citation=enriched.original_url,
                        enriched=enriched,
                        verified=True,
                        verification_results=verification_results,
                        verified_source_url=openai_result.source_url,
                        confidence=openai_result.confidence
                    )
                else:
                    # OpenAI couldn't verify, add as failed attempt
                    verification_results.append(
                        SourceVerificationResult(
                            source_name="openai_web_search",
                            verified=False,
                            error=openai_result.error or openai_result.explanation or "Not found via OpenAI search"
                        )
                    )
            except Exception as e:
                logger.warning("OpenAI verification failed, falling back to manual search", error=str(e))
        
        # Fallback to manual verification if OpenAI not available or failed
        
        # 1. Verify DOI if available (highest priority)
        if enriched.doi:
            doi_result = await self.verify_doi(enriched.doi)
            verification_results.append(doi_result)
            
            # Crossref also uses DOI
            crossref_result = await self.verify_via_crossref(enriched)
            verification_results.append(crossref_result)
        
        # 2. Verify via PubMed (for medical/biological citations)
        if enriched.source_type == 'academic' or enriched.doi:
            pubmed_result = await self.verify_pubmed(enriched)
            verification_results.append(pubmed_result)
        
        # 3. Verify via Semantic Scholar (comprehensive academic search)
        if enriched.source_type == 'academic' or enriched.title or enriched.doi:
            semantic_result = await self.verify_via_semantic_scholar(enriched)
            verification_results.append(semantic_result)
        
        # 4. Verify via arXiv (for preprints and physics/math papers)
        if enriched.source_type == 'academic' or enriched.title:
            arxiv_result = await self.verify_via_arxiv(enriched)
            verification_results.append(arxiv_result)
        
        # 5. Verify via Google Scholar (for academic citations)
        if enriched.source_type == 'academic' or enriched.title:
            scholar_result = await self.verify_google_scholar(enriched)
            verification_results.append(scholar_result)
        
        # 6. Verify via ResearchGate (academic social network)
        if enriched.source_type == 'academic' or enriched.title or enriched.doi:
            researchgate_result = await self.verify_via_researchgate(enriched)
            verification_results.append(researchgate_result)
        
        # 7. Verify via Academia.edu
        if enriched.source_type == 'academic' or enriched.title or enriched.doi:
            academia_result = await self.verify_via_academia(enriched)
            verification_results.append(academia_result)
        
        # 8. Verify via SSRN (social science research)
        if enriched.source_type == 'academic' or enriched.title:
            ssrn_result = await self.verify_via_ssrn(enriched)
            verification_results.append(ssrn_result)
        
        # 9. Verify via CourtListener (for legal citations)
        if enriched.source_type == 'legal' or 'court' in enriched.original_url.lower():
            court_result = await self.verify_courtlistener(enriched)
            verification_results.append(court_result)
        
        # 10. Verify web URL if it's a direct URL
        if enriched.original_url.startswith(('http://', 'https://', 'www.')):
            web_result = await self.verify_web_url(enriched.original_url)
            verification_results.append(web_result)
        
        # 11. General web search (as last resort - searches everywhere)
        if not any(r.verified for r in verification_results):
            web_search_result = await self.verify_via_web_search(enriched)
            verification_results.append(web_search_result)
        
        # Determine overall verification status
        verified = any(r.verified for r in verification_results)
        verified_result = next(
            (r for r in verification_results if r.verified),
            None
        )
        
        # Calculate overall confidence (max of all verified sources)
        confidence = max(
            (r.confidence for r in verification_results if r.verified),
            default=0.0
        )
        
        return CitationVerificationReport(
            original_citation=enriched.original_url,
            enriched=enriched,
            verified=verified,
            verification_results=verification_results,
            verified_source_url=verified_result.source_url if verified_result else None,
            confidence=confidence
        )
