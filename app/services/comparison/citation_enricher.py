"""Service for enriching citations with metadata and verifying across multiple sources."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EnrichedCitation:
    """Enriched citation with extracted metadata."""
    
    original_url: str
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    source_type: Optional[str] = None  # 'academic', 'legal', 'web', 'unknown'
    extracted_text: Optional[str] = None  # Text context where citation was found


class CitationEnricher:
    """Service for enriching citations with metadata."""
    
    def __init__(self, timeout: int = 10, ai_service: Optional[object] = None):
        """Initialize citation enricher.
        
        Args:
            timeout: HTTP request timeout in seconds
            ai_service: Optional AI service for intelligent metadata extraction
        """
        self.timeout = timeout
        self.ai_service = ai_service
        self._client: Optional[httpx.AsyncClient] = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AI-Audit/1.0; Citation-Enricher)"
                }
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def extract_doi(self, text: str) -> Optional[str]:
        """Extract DOI from text.
        
        Args:
            text: Text to search for DOI
            
        Returns:
            DOI string if found, None otherwise
        """
        # DOI pattern: 10.xxxx/xxxxx
        doi_pattern = r'10\.\d+/[^\s\)\]\>]+'
        match = re.search(doi_pattern, text, re.IGNORECASE)
        if match:
            doi = match.group(0).rstrip('.,;:!?)')
            return doi
        return None
    
    def extract_citation_metadata(self, citation_text: str, context: str = "") -> EnrichedCitation:
        """Extract metadata from citation text.
        
        Args:
            citation_text: The citation text or URL
            context: Surrounding context text
            
        Returns:
            EnrichedCitation with extracted metadata
        """
        enriched = EnrichedCitation(original_url=citation_text, extracted_text=context)
        
        combined_text = citation_text + " " + context
        
        # Extract DOI (priority - most reliable)
        doi = self.extract_doi(combined_text)
        if doi:
            enriched.doi = doi
            enriched.source_type = 'academic'
        
        # Extract year (4-digit year, typically 1900-2100)
        year_pattern = r'\b(19|20)\d{2}\b'
        year_matches = re.findall(year_pattern, combined_text)
        if year_matches:
            # Get valid 4-digit years only
            years = []
            for match in year_matches:
                if len(match) == 2:
                    try:
                        year = int(match[0] + match[1])
                        # Only accept reasonable years (1900-2100)
                        if 1900 <= year <= 2100:
                            years.append(year)
                    except ValueError:
                        pass
            if years:
                enriched.year = max(years)  # Most recent year
        
        # Extract authors - improved patterns to handle various citation formats
        # Pattern 1: "authored by X et al." or "by X et al."
        et_al_pattern = r'(?:authored\s+by|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+et\s+al\.?'
        et_al_match = re.search(et_al_pattern, combined_text, re.IGNORECASE)
        if et_al_match:
            author_name = et_al_match.group(1).strip()
            if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$', author_name):
                enriched.authors = [author_name + " et al."]
        
        # Pattern 2: "by X, Y, and Z" or "by X, Y, Z" (comma-separated list)
        if not enriched.authors:
            comma_authors_pattern = r'(?:authored\s+by|by)\s+((?:[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?:\s*,\s*(?:and\s+)?(?:[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))+)\s*(?:\(|,|\.|$)'
            comma_match = re.search(comma_authors_pattern, combined_text, re.IGNORECASE)
            if comma_match:
                authors_str = comma_match.group(1).strip()
                # Split by comma and "and", clean up
                authors_list = re.split(r',\s*(?:and\s+)?', authors_str)
                authors_clean = []
                for author in authors_list:
                    author = author.strip()
                    # Remove trailing year if present
                    author = re.sub(r'\s*\(\d{4}\)\s*$', '', author)
                    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$', author):
                        authors_clean.append(author)
                if authors_clean:
                    enriched.authors = authors_clean[:5]
        
        # Pattern 3: "X and Y" or "X & Y" (two authors)
        if not enriched.authors:
            two_authors_pattern = r'(?:authored\s+by|by)\s+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:and|&)\s+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
            two_match = re.search(two_authors_pattern, combined_text, re.IGNORECASE)
            if two_match:
                author1 = two_match.group(1).strip()
                author2 = two_match.group(2).strip()
                authors_list = []
                for author in [author1, author2]:
                    author = re.sub(r'\s*\(\d{4}\)\s*$', '', author)
                    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$', author):
                        authors_list.append(author)
                if authors_list:
                    enriched.authors = authors_list[:5]
        
        # Pattern 4: Single author "by X" or "authored by X"
        if not enriched.authors:
            single_author_pattern = r'(?:authored\s+by|by)\s+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:\(|,|\.|$)'
            single_match = re.search(single_author_pattern, combined_text, re.IGNORECASE)
            if single_match:
                author = single_match.group(1).strip()
                author = re.sub(r'\s*\(\d{4}\)\s*$', '', author)
                if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$', author):
                    enriched.authors = [author]
        
        # Pattern 5: "X et al." without "by" prefix
        if not enriched.authors:
            standalone_et_al = r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+et\s+al\.?\s*(?:\(|,|\.|$)'
            standalone_match = re.search(standalone_et_al, combined_text)
            if standalone_match:
                author_name = standalone_match.group(1).strip()
                if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', author_name):
                    enriched.authors = [author_name + " et al."]
        
        # Pattern 6: "X (Year)" format
        if not enriched.authors:
            author_year_pattern = r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+\((\d{4})\)'
            author_year_match = re.search(author_year_pattern, combined_text)
            if author_year_match:
                author = author_year_match.group(1).strip()
                if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$', author):
                    enriched.authors = [author]
        
        # Detect source type based on URL patterns and context
        text_lower = combined_text.lower()
        citation_lower = citation_text.lower()
        
        # Check for academic indicators
        if any(keyword in text_lower for keyword in ['doi:', 'doi', 'pubmed', 'pmid', 'arxiv', 'scholar', 'journal', 'article', 'paper', 'research', 'study']):
            enriched.source_type = 'academic'
        # Check for legal indicators
        elif any(keyword in text_lower for keyword in ['court', 'case', 'law', 'legal', 'courtlistener', 'supreme court', 'v.', 'vs.']):
            enriched.source_type = 'legal'
        # Check if it's a URL
        elif citation_text.startswith(('http://', 'https://', 'www.')):
            # Determine if academic URL
            if any(domain in citation_lower for domain in ['scholar', 'pubmed', 'arxiv', 'researchgate', 'academia', 'ssrn', 'crossref', 'doi.org', 'jstor', 'ieee', 'acm']):
                enriched.source_type = 'academic'
            elif any(domain in citation_lower for domain in ['court', 'law', 'legal', 'courtlistener']):
                enriched.source_type = 'legal'
            else:
                enriched.source_type = 'web'
        else:
            enriched.source_type = 'unknown'
        
        # Extract title - improved patterns to handle various citation formats
        # Priority 1: "titled 'Title'" or "titled "Title"" pattern (most common in test responses)
        title_patterns = [
            r'titled\s+["\']([^"\']{10,200})["\']',  # "titled 'Title'"
            r'entitled\s+["\']([^"\']{10,200})["\']',  # "entitled 'Title'"
            r'paper\s+(?:published|titled)\s+["\']([^"\']{10,200})["\']',  # "paper titled 'Title'"
            r'article\s+(?:published|titled)\s+["\']([^"\']{10,200})["\']',  # "article titled 'Title'"
            r'study\s+(?:published|titled)\s+["\']([^"\']{10,200})["\']',  # "study titled 'Title'"
            r'called\s+["\']([^"\']{10,200})["\']',  # "called 'Title'"
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # Validate title - must be reasonable length and not a URL
                if 10 < len(title) < 300:
                    if not title.startswith(('http://', 'https://', 'www.')) and '://' not in title:
                        enriched.title = title
                        break
        
        # Priority 2: Quoted text near citation (if no "titled" pattern found)
        if not enriched.title:
            # Look for quoted text in context, but prioritize longer quotes
            quoted_pattern = r'["\']([^"\']{15,200})["\']'
            quoted_matches = list(re.finditer(quoted_pattern, combined_text))
            if quoted_matches:
                # Prefer longer quotes (likely titles)
                best_match = max(quoted_matches, key=lambda m: len(m.group(1)))
                title = best_match.group(1).strip()
                # Filter out URLs and common false positives
                if (10 < len(title) < 300 and 
                    not title.startswith(('http://', 'https://', 'www.')) and 
                    '://' not in title and
                    not any(word in title.lower() for word in ['doi:', 'pmid:', 'http', 'www'])):
                    enriched.title = title
        
        # Priority 3: Look for capitalized title-like phrases (fallback)
        if not enriched.title and context:
            # Look for sequences of capitalized words that look like titles
            # Pattern: 3+ capitalized words in a row
            title_candidates = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){2,})\b', context)
            for candidate in title_candidates:
                # Filter out common false positives and validate format
                if (15 < len(candidate) < 200 and
                    not any(word in candidate.lower() for word in ['according', 'research', 'study', 'paper', 'article', 'published', 'doi', 'pmid', 'http']) and
                    not candidate.startswith(('http://', 'https://', 'www.'))):
                    enriched.title = candidate.strip()
                    break
        
        # Clean up title - remove common prefixes/suffixes and validate
        if enriched.title:
            # Remove prefixes
            enriched.title = re.sub(r'^(according to|see|from|source:|reference:|the|a|an)\s+', '', enriched.title, flags=re.IGNORECASE)
            enriched.title = enriched.title.strip()
            # Remove trailing punctuation but keep if it's part of the title
            enriched.title = re.sub(r'^["\']+|["\']+$', '', enriched.title)
            enriched.title = enriched.title.strip()[:200]
            
            # Final validation - never use URL as title
            if (enriched.title.startswith(('http://', 'https://', 'www.')) or 
                '://' in enriched.title or
                enriched.title.lower().startswith('doi:') or
                enriched.title.lower().startswith('pmid:')):
                enriched.title = None
        
        return enriched
    
    async def _extract_metadata_with_openai(self, html_content: str, url: str) -> dict:
        """Use OpenAI to intelligently extract metadata from HTML content.
        
        Args:
            html_content: HTML content from the URL
            url: The URL being processed
            
        Returns:
            Dictionary with extracted metadata (title, authors, year, journal, etc.)
        """
        if not self.ai_service:
            return {}
        
        # Clean HTML - extract text content (remove scripts, styles, etc.)
        # Keep only visible text and metadata
        text_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        text_content = re.sub(r'<style[^>]*>.*?</style>', '', text_content, flags=re.DOTALL | re.IGNORECASE)
        text_content = re.sub(r'<[^>]+>', ' ', text_content)
        text_content = re.sub(r'\s+', ' ', text_content).strip()[:5000]  # Limit to 5000 chars
        
        prompt = f"""Extract the following metadata from this web page content. Focus on finding the ACTUAL PAPER/RESOURCE title, not the website name or journal name.

URL: {url}

Page Content (first 5000 chars):
{text_content}

Extract and return ONLY valid JSON with this exact structure:
{{
    "title": "The actual paper/article/resource title (not journal name or website name)",
    "authors": ["Author1 Full Name", "Author2 Full Name", ...],
    "year": 2023,
    "journal": "Journal Name if available",
    "doi": "DOI if found in content"
}}

CRITICAL RULES:
- "title" should be the ACTUAL paper/article/resource title, NOT the journal name or website name
- If you see "New England Journal of Medicine" in the title tag, that's the JOURNAL, not the paper title
- Look for the actual paper title in the content (usually in headings, metadata, or main text)
- Extract authors as full names (First Last or First Middle Last)
- Extract year as 4-digit number
- If any field cannot be found, use null (not empty string)
- Return ONLY the JSON, no other text

JSON:"""

        try:
            response = await self.ai_service.get_response(
                "openai",
                prompt,
                system_prompt="You are an expert at extracting academic paper metadata from web pages. Always return valid JSON only."
            )
            
            # Parse JSON from response
            # Try to extract JSON from response (might have markdown code blocks)
            import json
            
            # Remove markdown code blocks if present
            response_clean = response.strip()
            if response_clean.startswith('```'):
                # Remove ```json or ``` markers
                response_clean = re.sub(r'^```(?:json)?\s*', '', response_clean, flags=re.MULTILINE)
                response_clean = re.sub(r'\s*```\s*$', '', response_clean, flags=re.MULTILINE)
            
            # Try to find JSON object in response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_clean, re.DOTALL)
            if json_match:
                try:
                    metadata = json.loads(json_match.group(0))
                    # Validate required structure
                    if isinstance(metadata, dict):
                        return metadata
                except json.JSONDecodeError:
                    pass
            
            # Try parsing entire response as JSON
            try:
                metadata = json.loads(response_clean)
                if isinstance(metadata, dict):
                    return metadata
            except json.JSONDecodeError:
                pass
                
        except Exception as e:
            logger.debug("Failed to extract metadata with OpenAI", url=url, error=str(e))
        
        return {}
    
    def _extract_metadata_from_html(self, html_content: str) -> dict:
        """Extract metadata from HTML using regex patterns.
        
        Args:
            html_content: HTML content
            
        Returns:
            Dictionary with extracted metadata
        """
        metadata = {}
        
        # Try to find title in various HTML elements
        # Priority 1: Look for meta tags
        meta_title = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        if meta_title:
            metadata['title'] = meta_title.group(1).strip()
        else:
            # Priority 2: Look for h1 or main heading
            h1_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html_content, re.IGNORECASE | re.DOTALL)
            if h1_match:
                title = re.sub(r'\s+', ' ', h1_match.group(1)).strip()
                # Filter out journal names
                if not any(journal in title.lower() for journal in ['new england journal', 'journal of', 'nature', 'science', 'cell']):
                    metadata['title'] = title[:200]
        
        # Extract authors from meta tags or content
        author_patterns = [
            r'<meta\s+name=["\']citation_author["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+property=["\']article:author["\']\s+content=["\']([^"\']+)["\']',
        ]
        authors = []
        for pattern in author_patterns:
            matches = re.finditer(pattern, html_content, re.IGNORECASE)
            for match in matches:
                author = match.group(1).strip()
                if author and len(author) > 5:
                    authors.append(author)
        if authors:
            metadata['authors'] = authors[:5]
        
        # Extract year
        year_match = re.search(r'<meta\s+name=["\']citation_publication_date["\']\s+content=["\'](\d{4})', html_content, re.IGNORECASE)
        if year_match:
            try:
                metadata['year'] = int(year_match.group(1))
            except ValueError:
                pass
        
        # Extract journal
        journal_match = re.search(r'<meta\s+name=["\']citation_journal_title["\']\s+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        if journal_match:
            metadata['journal'] = journal_match.group(1).strip()
        
        return metadata
    
    async def enrich_citation(self, citation_text: str, context: str = "") -> EnrichedCitation:
        """Enrich a citation with metadata.
        
        Args:
            citation_text: The citation text or URL
            context: Surrounding context text
            
        Returns:
            EnrichedCitation with metadata
        """
        # Start with basic extraction
        enriched = self.extract_citation_metadata(citation_text, context)
        
        # If it's a URL, try to fetch and extract more metadata
        if citation_text.startswith(('http://', 'https://', 'www.')):
            try:
                client = self._get_client()
                response = await client.get(citation_text)
                if response.status_code == 200:
                    html_content = response.text
                    
                    # First, try regex-based extraction (faster)
                    html_metadata = self._extract_metadata_from_html(html_content)
                    
                    # Update enriched with HTML metadata (only if not already set)
                    if html_metadata.get('title') and not enriched.title:
                        enriched.title = html_metadata['title']
                    if html_metadata.get('authors') and not enriched.authors:
                        enriched.authors = html_metadata['authors']
                    if html_metadata.get('year') and not enriched.year:
                        enriched.year = html_metadata['year']
                    if html_metadata.get('journal') and not enriched.journal:
                        enriched.journal = html_metadata['journal']
                    
                    # If we still don't have title or authors, use OpenAI for intelligent extraction
                    if self.ai_service and (not enriched.title or not enriched.authors):
                        openai_metadata = await self._extract_metadata_with_openai(html_content, citation_text)
                        
                        # Update with OpenAI-extracted metadata (prioritize OpenAI results)
                        if openai_metadata.get('title'):
                            enriched.title = openai_metadata['title']
                        if openai_metadata.get('authors'):
                            enriched.authors = openai_metadata['authors']
                        if openai_metadata.get('year') and not enriched.year:
                            enriched.year = openai_metadata['year']
                        if openai_metadata.get('journal') and not enriched.journal:
                            enriched.journal = openai_metadata['journal']
                        if openai_metadata.get('doi') and not enriched.doi:
                            enriched.doi = openai_metadata['doi']
                    
                    # Clean up title - remove journal names and validate
                    if enriched.title:
                        # Remove common journal name prefixes/suffixes
                        enriched.title = re.sub(r'^\s*(New England Journal|Journal of|Nature|Science|Cell)\s*[-–—]\s*', '', enriched.title, flags=re.IGNORECASE)
                        enriched.title = re.sub(r'\s*[-–—]\s*(New England Journal|Journal of|Nature|Science|Cell)\s*$', '', enriched.title, flags=re.IGNORECASE)
                        enriched.title = enriched.title.strip()[:200]
                        
                        # Final validation - don't use if it's just a journal name
                        if any(journal in enriched.title.lower() for journal in ['new england journal', 'journal of medicine', 'nature', 'science magazine']):
                            if len(enriched.title) < 30:  # Likely just journal name
                                enriched.title = None
            except Exception as e:
                logger.debug("Failed to fetch citation URL", url=citation_text, error=str(e))
        
        return enriched
