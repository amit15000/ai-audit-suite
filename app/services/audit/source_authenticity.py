"""Service for checking source authenticity and citation verification."""
from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class SourceAuthenticityChecker:
    """Checks if URLs, papers, and citations exist and are authentic."""

    def __init__(self):
        self.ai_service = AIPlatformService()
        self._http_client = httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=10)
        )

    async def check_authenticity(
        self,
        response: str,
        judge_platform_id: str = "openai",
        platform_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Check source authenticity in the response.
        
        Args:
            response: The AI response to check
            judge_platform_id: Platform to use for analysis
            
        Returns:
            Dictionary with authenticity score (0-10), findings, and details
        """
        findings = []
        score = 10  # Start with perfect score
        
        # 0. Extract sources from provider metadata (e.g., Gemini grounding, OpenAI citations)
        provider_sources = self._extract_provider_sources(platform_metadata or {})
        provider_urls = provider_sources.get("urls", [])
        provider_citations = provider_sources.get("citations", [])
        
        # 1. Extract URLs from response text
        urls = self._extract_urls(response)
        # Combine with provider URLs (deduplicate)
        all_urls = list(set(urls + provider_urls))
        url_results = []
        for url in all_urls:
            url_check = await self._check_url(url)
            url_results.append(url_check)
            if not url_check["exists"]:
                findings.append({
                    "type": "invalid_url",
                    "severity": "high",
                    "url": url,
                    "reason": url_check.get("reason", "URL does not exist or is inaccessible")
                })
                score -= 2  # Deduct 2 points per invalid URL
        
        # 2. Extract and check citations from response text
        citations = self._extract_citations(response)
        # Combine with provider citations (deduplicate)
        all_citations = list(set(citations + provider_citations))
        citation_results = []
        for citation in all_citations:
            citation_check = await self._check_citation(citation, judge_platform_id)
            citation_results.append(citation_check)
            if not citation_check["exists"]:
                findings.append({
                    "type": "fake_citation",
                    "severity": "high",
                    "citation": citation,
                    "reason": citation_check.get("reason", "Citation does not exist")
                })
                score -= 3  # Deduct 3 points per fake citation
        
        # 3. Check for legal references
        legal_refs = self._extract_legal_references(response)
        legal_results = []
        for ref in legal_refs:
            legal_check = await self._check_legal_reference(ref, judge_platform_id)
            legal_results.append(legal_check)
            if not legal_check["exists"]:
                findings.append({
                    "type": "invalid_legal_reference",
                    "severity": "high",
                    "reference": ref,
                    "reason": legal_check.get("reason", "Legal reference does not exist")
                })
                score -= 3  # Deduct 3 points per invalid legal reference
        
        # 4. Check for research papers (DOI, arXiv, etc.)
        papers = self._extract_papers(response)
        paper_results = []
        for paper in papers:
            paper_check = await self._check_paper(paper)
            paper_results.append(paper_check)
            if not paper_check["exists"]:
                findings.append({
                    "type": "fake_paper",
                    "severity": "high",
                    "paper": paper,
                    "reason": paper_check.get("reason", "Paper does not exist")
                })
                score -= 3  # Deduct 3 points per fake paper
        
        # Ensure score is between 0-10
        score = max(0, min(10, score))
        
        total_sources = len(all_urls) + len(all_citations) + len(legal_refs) + len(papers)
        valid_sources = (
            sum(1 for r in url_results if r["exists"]) +
            sum(1 for r in citation_results if r["exists"]) +
            sum(1 for r in legal_results if r["exists"]) +
            sum(1 for r in paper_results if r["exists"])
        )
        
        provider_sources_checked = len(provider_urls) + len(provider_citations)
        
        return {
            "score": score,
            "total_sources": total_sources,
            "valid_sources": valid_sources,
            "invalid_sources": total_sources - valid_sources,
            "urls_checked": len(all_urls),
            "citations_checked": len(all_citations),
            "legal_refs_checked": len(legal_refs),
            "papers_checked": len(papers),
            "provider_sources_checked": provider_sources_checked,
            "findings": findings,
            "explanation": self._generate_explanation(
                score, valid_sources, total_sources, provider_sources_checked
            )
        }

    def _extract_urls(self, text: str) -> list[str]:
        """Extract URLs from text."""
        url_pattern = r'https?://[^\s\)]+'
        urls = re.findall(url_pattern, text)
        # Clean up URLs (remove trailing punctuation)
        cleaned_urls = []
        for url in urls:
            url = url.rstrip('.,;:!?)')
            if url not in cleaned_urls:
                cleaned_urls.append(url)
        return cleaned_urls

    def _extract_citations(self, text: str) -> list[str]:
        """Extract citation patterns from text."""
        citations = []
        
        # Pattern 1: [1], [2], etc.
        numbered_citations = re.findall(r'\[(\d+)\]', text)
        citations.extend([f"[{num}]" for num in numbered_citations])
        
        # Pattern 2: (Author, Year)
        author_year = re.findall(r'\(([A-Z][a-z]+(?:\s+et\s+al\.)?,\s*\d{4})\)', text)
        citations.extend(author_year)
        
        # Pattern 3: Author et al. (Year)
        author_et_al = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+et\s+al\.\s*\(\d{4}\))', text)
        citations.extend(author_et_al)
        
        return list(set(citations))  # Remove duplicates

    def _extract_legal_references(self, text: str) -> list[str]:
        """Extract legal references (cases, statutes, etc.)."""
        legal_refs = []
        
        # Pattern: Case names (e.g., "Roe v. Wade", "Brown v. Board of Education")
        case_pattern = r'([A-Z][a-z]+(?:\s+[a-z]+)?\s+v\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        cases = re.findall(case_pattern, text)
        legal_refs.extend(cases)
        
        # Pattern: Statutes (e.g., "42 U.S.C. § 1983", "GDPR Article 6")
        statute_patterns = [
            r'\d+\s+U\.S\.C\.\s+§\s+\d+',
            r'GDPR\s+Article\s+\d+',
            r'[A-Z]+\s+Article\s+\d+',
        ]
        for pattern in statute_patterns:
            statutes = re.findall(pattern, text)
            legal_refs.extend(statutes)
        
        return list(set(legal_refs))

    def _extract_papers(self, text: str) -> list[str]:
        """Extract research paper references."""
        papers = []
        
        # Pattern: DOI (e.g., "doi:10.1234/example")
        doi_pattern = r'doi:10\.\d+/[^\s\)]+'
        dois = re.findall(doi_pattern, text, re.IGNORECASE)
        papers.extend(dois)
        
        # Pattern: arXiv (e.g., "arXiv:1234.5678")
        arxiv_pattern = r'arxiv:\d+\.\d+'
        arxiv_ids = re.findall(arxiv_pattern, text, re.IGNORECASE)
        papers.extend(arxiv_ids)
        
        # Pattern: PubMed (e.g., "PMID:12345678")
        pubmed_pattern = r'PMID:\d+'
        pubmed_ids = re.findall(pubmed_pattern, text, re.IGNORECASE)
        papers.extend(pubmed_ids)
        
        return list(set(papers))

    async def _check_url(self, url: str) -> dict[str, Any]:
        """Check if a URL exists and is accessible."""
        try:
            response = await self._http_client.head(url, follow_redirects=True)
            if response.status_code < 400:
                return {"exists": True, "status_code": response.status_code}
            else:
                return {
                    "exists": False,
                    "status_code": response.status_code,
                    "reason": f"HTTP {response.status_code}"
                }
        except httpx.TimeoutException:
            return {"exists": False, "reason": "Request timeout"}
        except httpx.RequestError as e:
            return {"exists": False, "reason": f"Request failed: {str(e)[:100]}"}
        except Exception as e:
            logger.debug("source_authenticity.url_check_failed", url=url, error=str(e))
            return {"exists": False, "reason": "Unknown error"}

    async def _check_citation(self, citation: str, judge_platform_id: str) -> dict[str, Any]:
        """Check if a citation exists (using LLM to verify)."""
        verification_prompt = f"""Verify if the following citation exists and is authentic:

Citation: {citation}

Return a JSON object with:
{{
    "exists": true/false,
    "reason": "<explanation>",
    "confidence": "high|medium|low"
}}

Only mark as existing if you are confident this is a real, verifiable citation."""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                verification_prompt,
                system_prompt="You are an expert at verifying academic citations. Only mark citations as existing if you are confident they are real."
            )
            
            import json
            json_match = re.search(r'\{.*"exists".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    exists = result.get("exists", False)
                    confidence = result.get("confidence", "low")
                    # Only trust high confidence verifications
                    if exists and confidence == "high":
                        return {"exists": True, "reason": result.get("reason", "Verified")}
                    else:
                        return {
                            "exists": False,
                            "reason": result.get("reason", "Citation not found or unverifiable")
                        }
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("source_authenticity.citation_check_failed", error=str(e))
        
        return {"exists": False, "reason": "Unable to verify citation"}

    async def _check_legal_reference(self, ref: str, judge_platform_id: str) -> dict[str, Any]:
        """Check if a legal reference exists."""
        verification_prompt = f"""Verify if the following legal reference exists and is authentic:

Legal Reference: {ref}

Return a JSON object with:
{{
    "exists": true/false,
    "reason": "<explanation>",
    "confidence": "high|medium|low"
}}

Only mark as existing if you are confident this is a real legal case, statute, or regulation."""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                verification_prompt,
                system_prompt="You are an expert at verifying legal references. Only mark references as existing if you are confident they are real."
            )
            
            import json
            json_match = re.search(r'\{.*"exists".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    exists = result.get("exists", False)
                    confidence = result.get("confidence", "low")
                    if exists and confidence == "high":
                        return {"exists": True, "reason": result.get("reason", "Verified")}
                    else:
                        return {
                            "exists": False,
                            "reason": result.get("reason", "Legal reference not found")
                        }
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("source_authenticity.legal_ref_check_failed", error=str(e))
        
        return {"exists": False, "reason": "Unable to verify legal reference"}

    async def _check_paper(self, paper_ref: str) -> dict[str, Any]:
        """Check if a research paper exists."""
        paper_ref_lower = paper_ref.lower()
        
        # Check DOI
        if paper_ref_lower.startswith("doi:"):
            doi = paper_ref.replace("doi:", "").replace("DOI:", "")
            return await self._check_doi(doi)
        
        # Check arXiv
        if paper_ref_lower.startswith("arxiv:"):
            arxiv_id = paper_ref.replace("arxiv:", "").replace("arXiv:", "")
            return await self._check_arxiv(arxiv_id)
        
        # Check PubMed
        if paper_ref_lower.startswith("pmid:"):
            pmid = paper_ref.replace("pmid:", "").replace("PMID:", "")
            return await self._check_pubmed(pmid)
        
        return {"exists": False, "reason": "Unknown paper reference format"}

    async def _check_doi(self, doi: str) -> dict[str, Any]:
        """Check if a DOI exists."""
        try:
            # Use DOI.org API
            doi_url = f"https://doi.org/{doi}"
            response = await self._http_client.head(doi_url, follow_redirects=True)
            if response.status_code < 400:
                return {"exists": True, "reason": "DOI verified"}
            else:
                return {"exists": False, "reason": f"DOI not found (HTTP {response.status_code})"}
        except Exception as e:
            logger.debug("source_authenticity.doi_check_failed", doi=doi, error=str(e))
            return {"exists": False, "reason": "Unable to verify DOI"}

    async def _check_arxiv(self, arxiv_id: str) -> dict[str, Any]:
        """Check if an arXiv paper exists."""
        try:
            # Use arXiv API
            arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
            response = await self._http_client.head(arxiv_url, follow_redirects=True)
            if response.status_code < 400:
                return {"exists": True, "reason": "arXiv paper verified"}
            else:
                return {"exists": False, "reason": f"arXiv paper not found (HTTP {response.status_code})"}
        except Exception as e:
            logger.debug("source_authenticity.arxiv_check_failed", arxiv_id=arxiv_id, error=str(e))
            return {"exists": False, "reason": "Unable to verify arXiv paper"}

    async def _check_pubmed(self, pmid: str) -> dict[str, Any]:
        """Check if a PubMed ID exists."""
        try:
            # Use PubMed API
            pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            response = await self._http_client.head(pubmed_url, follow_redirects=True)
            if response.status_code < 400:
                return {"exists": True, "reason": "PubMed ID verified"}
            else:
                return {"exists": False, "reason": f"PubMed ID not found (HTTP {response.status_code})"}
        except Exception as e:
            logger.debug("source_authenticity.pubmed_check_failed", pmid=pmid, error=str(e))
            return {"exists": False, "reason": "Unable to verify PubMed ID"}

    def _extract_provider_sources(self, metadata: dict[str, Any]) -> dict[str, list[str]]:
        """Extract sources from provider metadata (e.g., Gemini grounding, OpenAI citations).
        
        Returns:
            dict with 'urls' and 'citations' lists
        """
        sources = {"urls": [], "citations": []}
        
        if not metadata:
            return sources
        
        # Check for Gemini grounding metadata
        # Gemini returns grounding metadata in candidates[0].groundingMetadata
        if "candidates" in metadata and isinstance(metadata["candidates"], list):
            for candidate in metadata["candidates"]:
                if "groundingMetadata" in candidate:
                    grounding = candidate["groundingMetadata"]
                    # Extract web search results
                    if "webSearchQueries" in grounding:
                        # These are queries, not URLs, but we can note them
                        pass
                    # Extract grounding chunks which may contain URLs
                    if "groundingChunks" in grounding:
                        for chunk in grounding.get("groundingChunks", []):
                            if "web" in chunk:
                                web_info = chunk["web"]
                                if "uri" in web_info:
                                    sources["urls"].append(web_info["uri"])
        
        # Check for OpenAI citations (if they add this feature)
        # OpenAI might return citations in metadata.citations or similar
        if "citations" in metadata:
            citations = metadata["citations"]
            if isinstance(citations, list):
                for citation in citations:
                    if isinstance(citation, str):
                        sources["citations"].append(citation)
                    elif isinstance(citation, dict):
                        # Extract URL if present
                        if "url" in citation:
                            sources["urls"].append(citation["url"])
                        if "text" in citation:
                            sources["citations"].append(citation["text"])
        
        # Check for Perplexity sources (they return sources in metadata)
        if "sources" in metadata:
            sources_list = metadata["sources"]
            if isinstance(sources_list, list):
                for source in sources_list:
                    if isinstance(source, str):
                        if source.startswith("http"):
                            sources["urls"].append(source)
                        else:
                            sources["citations"].append(source)
                    elif isinstance(source, dict):
                        if "url" in source:
                            sources["urls"].append(source["url"])
                        if "title" in source:
                            sources["citations"].append(source["title"])
        
        # Remove duplicates
        sources["urls"] = list(set(sources["urls"]))
        sources["citations"] = list(set(sources["citations"]))
        
        return sources

    def _generate_explanation(
        self, 
        score: int, 
        valid_sources: int, 
        total_sources: int,
        provider_sources_checked: int = 0,
    ) -> str:
        """Generate explanation for the authenticity score."""
        if total_sources == 0:
            return "No sources found in the response to verify."
        
        base_parts = []
        if score >= 8:
            base_parts.append(f"High source authenticity: {valid_sources} out of {total_sources} sources verified")
        elif score >= 5:
            base_parts.append(f"Moderate source authenticity: {valid_sources} out of {total_sources} sources verified")
        else:
            base_parts.append(f"Low source authenticity: Only {valid_sources} out of {total_sources} sources verified")
        
        if provider_sources_checked > 0:
            base_parts.append(f"({provider_sources_checked} from provider metadata)")
        
        return ". ".join(base_parts) + "."

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._http_client.aclose()

