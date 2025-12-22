"""Tests for fabricated citations score calculation."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.comparison.citation_verifier import Citation, CitationVerificationResult
from app.services.comparison.hallucination.fabricated_citations import FabricatedCitationsScorer
from app.services.llm.ai_platform_service import AIPlatformService


class TestFabricatedCitationsScorer:
    """Tests for FabricatedCitationsScorer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.citation_verifier = MagicMock()
        self.ai_service = MagicMock(spec=AIPlatformService)
        self.scorer = FabricatedCitationsScorer(self.citation_verifier, self.ai_service)

    @pytest.mark.asyncio
    async def test_no_citations_returns_neutral_score(self):
        """Test that response with no citations returns neutral score."""
        response = "This is a response without any citations."
        
        # Mock: no citations found
        self.citation_verifier.extract_citations.return_value = []
        
        score = await self.scorer.calculate_score(
            response, "openai", use_llm=False
        )
        
        assert score == 6  # Neutral score when no citations
        self.citation_verifier.extract_citations.assert_called_once_with(response)

    @pytest.mark.asyncio
    async def test_all_valid_citations_high_score(self):
        """Test that all valid citations result in high score."""
        response = "According to https://example.com/article1 and https://example.com/article2, the data shows..."
        
        # Create mock citations
        citation1 = Citation(
            url="https://example.com/article1",
            text="https://example.com/article1",
            position=15,
            context="According to https://example.com/article1"
        )
        citation2 = Citation(
            url="https://example.com/article2",
            text="https://example.com/article2",
            position=50,
            context="and https://example.com/article2"
        )
        
        # Create mock verification results - all accessible
        result1 = CitationVerificationResult(
            citation=citation1,
            is_valid=True,
            is_accessible=True,
            status_code=200
        )
        result2 = CitationVerificationResult(
            citation=citation2,
            is_valid=True,
            is_accessible=True,
            status_code=200
        )
        
        # Mock methods
        self.citation_verifier.extract_citations.return_value = [citation1, citation2]
        self.citation_verifier.verify_all_citations = AsyncMock(
            return_value=[result1, result2]
        )
        
        score = await self.scorer.calculate_score(
            response, "openai", use_llm=False
        )
        
        # Should be high score (9.0-9.5) for all valid citations
        assert score >= 9
        assert score <= 10

    @pytest.mark.asyncio
    async def test_all_fabricated_citations_low_score(self):
        """Test that all fabricated citations result in low score."""
        response = "According to https://fake-url-that-does-not-exist.com/article1, the data shows..."
        
        # Create mock citations
        citation1 = Citation(
            url="https://fake-url-that-does-not-exist.com/article1",
            text="https://fake-url-that-does-not-exist.com/article1",
            position=15,
            context="According to https://fake-url-that-does-not-exist.com/article1"
        )
        
        # Create mock verification results - all inaccessible
        result1 = CitationVerificationResult(
            citation=citation1,
            is_valid=False,
            is_accessible=False,
            status_code=None,
            error="Connection failed"
        )
        
        # Mock methods
        self.citation_verifier.extract_citations.return_value = [citation1]
        self.citation_verifier.verify_all_citations = AsyncMock(
            return_value=[result1]
        )
        
        score = await self.scorer.calculate_score(
            response, "openai", use_llm=False
        )
        
        # Should be low score (1.0) for all fabricated citations
        assert score <= 2
        assert score >= 0

    @pytest.mark.asyncio
    async def test_mixed_citations_moderate_score(self):
        """Test that mixed valid and fabricated citations result in moderate score."""
        response = "According to https://example.com/article1 and https://fake-url.com/article2, the data shows..."
        
        # Create mock citations
        citation1 = Citation(
            url="https://example.com/article1",
            text="https://example.com/article1",
            position=15,
            context="According to https://example.com/article1"
        )
        citation2 = Citation(
            url="https://fake-url.com/article2",
            text="https://fake-url.com/article2",
            position=50,
            context="and https://fake-url.com/article2"
        )
        
        # Create mock verification results - one valid, one invalid
        result1 = CitationVerificationResult(
            citation=citation1,
            is_valid=True,
            is_accessible=True,
            status_code=200
        )
        result2 = CitationVerificationResult(
            citation=citation2,
            is_valid=False,
            is_accessible=False,
            status_code=None,
            error="Connection failed"
        )
        
        # Mock methods
        self.citation_verifier.extract_citations.return_value = [citation1, citation2]
        self.citation_verifier.verify_all_citations = AsyncMock(
            return_value=[result1, result2]
        )
        
        score = await self.scorer.calculate_score(
            response, "openai", use_llm=False
        )
        
        # Should be moderate score (around 6.0) for 50% fabricated
        assert score >= 3
        assert score <= 7

    @pytest.mark.asyncio
    async def test_with_llm_analysis(self):
        """Test that LLM analysis is used when use_llm=True."""
        response = "According to https://example.com/article1, the data shows..."
        
        # Create mock citations
        citation1 = Citation(
            url="https://example.com/article1",
            text="https://example.com/article1",
            position=15,
            context="According to https://example.com/article1"
        )
        
        # Create mock verification results
        result1 = CitationVerificationResult(
            citation=citation1,
            is_valid=True,
            is_accessible=True,
            status_code=200
        )
        
        # Mock LLM response
        llm_response = json.dumps({
            "score": 8,
            "fabrication_likelihood": 0.2,
            "explanation": "Citations appear legitimate",
            "fabricated_citations": [],
            "verified_citations": [1]
        })
        
        # Mock methods
        self.citation_verifier.extract_citations.return_value = [citation1]
        self.citation_verifier.verify_all_citations = AsyncMock(
            return_value=[result1]
        )
        self.ai_service.get_response = AsyncMock(return_value=llm_response)
        
        score = await self.scorer.calculate_score(
            response, "openai", use_llm=True
        )
        
        # Should call LLM
        self.ai_service.get_response.assert_called_once()
        assert 0 <= score <= 10

    @pytest.mark.asyncio
    async def test_llm_analysis_failure_fallback(self):
        """Test that LLM analysis failure falls back to base score."""
        response = "According to https://example.com/article1, the data shows..."
        
        # Create mock citations
        citation1 = Citation(
            url="https://example.com/article1",
            text="https://example.com/article1",
            position=15,
            context="According to https://example.com/article1"
        )
        
        # Create mock verification results
        result1 = CitationVerificationResult(
            citation=citation1,
            is_valid=True,
            is_accessible=True,
            status_code=200
        )
        
        # Mock LLM to raise exception
        self.citation_verifier.extract_citations.return_value = [citation1]
        self.citation_verifier.verify_all_citations = AsyncMock(
            return_value=[result1]
        )
        self.ai_service.get_response = AsyncMock(side_effect=Exception("API error"))
        
        score = await self.scorer.calculate_score(
            response, "openai", use_llm=True
        )
        
        # Should still return a valid score (fallback to base score)
        assert 0 <= score <= 10

    @pytest.mark.asyncio
    async def test_calculate_base_score_all_accessible(self):
        """Test base score calculation with all accessible citations."""
        citations = [
            Citation(url="https://example.com/1", text="", position=0, context=""),
            Citation(url="https://example.com/2", text="", position=0, context=""),
            Citation(url="https://example.com/3", text="", position=0, context=""),
        ]
        
        results = [
            CitationVerificationResult(citation=c, is_valid=True, is_accessible=True, status_code=200)
            for c in citations
        ]
        
        score = self.scorer._calculate_base_score_from_verification(results)
        
        # Should be high score (9.5) for 3+ accessible citations
        assert score == 9.5

    @pytest.mark.asyncio
    async def test_calculate_base_score_partial_fabrication(self):
        """Test base score calculation with partial fabrication."""
        citations = [
            Citation(url="https://example.com/1", text="", position=0, context=""),
            Citation(url="https://fake.com/2", text="", position=0, context=""),
        ]
        
        results = [
            CitationVerificationResult(
                citation=citations[0], is_valid=True, is_accessible=True, status_code=200
            ),
            CitationVerificationResult(
                citation=citations[1], is_valid=False, is_accessible=False, status_code=None
            ),
        ]
        
        score = self.scorer._calculate_base_score_from_verification(results)
        
        # Should be moderate score (6.0) for 50% fabricated
        assert score == 6.0

    @pytest.mark.asyncio
    async def test_parse_llm_response_valid_json(self):
        """Test parsing valid LLM JSON response."""
        llm_response = json.dumps({
            "score": 7,
            "fabrication_likelihood": 0.3,
            "explanation": "Some citations may be fabricated",
            "fabricated_citations": [2],
            "verified_citations": [1]
        })
        
        result = self.scorer._parse_llm_response(llm_response)
        
        assert result["score"] == 7.0
        assert result["fabrication_likelihood"] == 0.3
        assert result["explanation"] == "Some citations may be fabricated"
        assert result["fabricated_citations"] == [2]
        assert result["verified_citations"] == [1]

    @pytest.mark.asyncio
    async def test_parse_llm_response_invalid_json_fallback(self):
        """Test parsing invalid LLM response falls back gracefully."""
        llm_response = "This is not valid JSON"
        
        result = self.scorer._parse_llm_response(llm_response)
        
        # Should return default values
        assert "score" in result
        assert "fabrication_likelihood" in result
        assert result["fabrication_likelihood"] == 0.5  # Default neutral

    @pytest.mark.asyncio
    async def test_combine_scores(self):
        """Test score combination logic."""
        base_score = 8.0
        llm_analysis = {
            "score": 7.0,
            "fabrication_likelihood": 0.3
        }
        
        combined = self.scorer._combine_scores(base_score, llm_analysis)
        
        # Should be between 0 and 10
        assert 0 <= combined <= 10
        # Should be weighted combination
        # 60% base (8.0) + 40% LLM (7.0) = 4.8 + 2.8 = 7.6
        # Plus adjustment for likelihood: (0.5 - 0.3) * 4.0 = 0.8
        # Total: ~8.4
        assert 7.0 <= combined <= 9.0

    @pytest.mark.asyncio
    async def test_suspicious_url_patterns(self):
        """Test detection of suspicious URL patterns."""
        response = "According to https://example.com/test and https://placeholder.com/article, the data shows..."
        
        # Create mock citations with suspicious URLs
        citation1 = Citation(
            url="https://example.com/test",
            text="https://example.com/test",
            position=15,
            context="According to https://example.com/test"
        )
        citation2 = Citation(
            url="https://placeholder.com/article",
            text="https://placeholder.com/article",
            position=50,
            context="and https://placeholder.com/article"
        )
        
        # Create mock verification results - both inaccessible
        result1 = CitationVerificationResult(
            citation=citation1,
            is_valid=False,
            is_accessible=False,
            status_code=None,
            error="Connection failed"
        )
        result2 = CitationVerificationResult(
            citation=citation2,
            is_valid=False,
            is_accessible=False,
            status_code=None,
            error="Connection failed"
        )
        
        # Mock methods
        self.citation_verifier.extract_citations.return_value = [citation1, citation2]
        self.citation_verifier.verify_all_citations = AsyncMock(
            return_value=[result1, result2]
        )
        
        score = await self.scorer.calculate_score(
            response, "openai", use_llm=False
        )
        
        # Should be low score for suspicious/inaccessible URLs
        assert score <= 2

    @pytest.mark.asyncio
    async def test_empty_verification_results(self):
        """Test handling of empty verification results."""
        response = "This response has citations but verification failed."
        
        # Mock: citations found but verification returns empty
        citation1 = Citation(
            url="https://example.com/article1",
            text="https://example.com/article1",
            position=15,
            context="According to https://example.com/article1"
        )
        
        self.citation_verifier.extract_citations.return_value = [citation1]
        self.citation_verifier.verify_all_citations = AsyncMock(return_value=[])
        
        score = await self.scorer.calculate_score(
            response, "openai", use_llm=False
        )
        
        # Should return neutral score
        assert score == 6
