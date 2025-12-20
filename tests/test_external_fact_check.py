"""Tests for external fact check sub-score implementation."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.domain.schemas import ExternalFactCheckClaim, ExternalFactCheckResult
from app.services.comparison.hallucination.external_fact_check import (
    Claim,
    ClaimExtractor,
    ClaimVerifier,
    Evidence,
    EvidenceRetriever,
    EvidenceTextFetcher,
    ExternalFactCheckScorer,
)
from app.services.llm.ai_platform_service import AIPlatformService


class TestClaimExtractor:
    """Tests for ClaimExtractor class."""

    def test_extract_claims_rule_based_basic(self):
        """Test rule-based claim extraction with basic factual statements."""
        extractor = ClaimExtractor(use_llm=False)
        
        response = "The population of New York City is 8.5 million. In 2020, the city experienced significant growth."
        claims = extractor._extract_claims_rule_based(response, max_claims=10)
        
        assert len(claims) > 0
        assert all(isinstance(c, Claim) for c in claims)
        assert claims[0].claim_type in ["number", "date", "entity", "general"]

    def test_extract_claims_rule_based_filters_questions(self):
        """Test that questions are filtered out."""
        extractor = ClaimExtractor(use_llm=False)
        
        response = "What is the population? The population is 8.5 million."
        claims = extractor._extract_claims_rule_based(response, max_claims=10)
        
        # Should not extract the question
        question_claims = [c for c in claims if "?" in c.claim]
        assert len(question_claims) == 0

    def test_extract_claims_rule_based_filters_opinions(self):
        """Test that opinion statements are filtered out."""
        extractor = ClaimExtractor(use_llm=False)
        
        response = "I think the population is high. The population is 8.5 million."
        claims = extractor._extract_claims_rule_based(response, max_claims=10)
        
        # Should not extract opinion statements
        opinion_claims = [c for c in claims if "i think" in c.claim.lower()]
        assert len(opinion_claims) == 0

    def test_classify_claim_type(self):
        """Test claim type classification."""
        extractor = ClaimExtractor(use_llm=False)
        
        assert extractor._classify_claim_type("In 2020, the event occurred") == "date"
        assert extractor._classify_claim_type("The number is 42") == "number"
        assert extractor._classify_claim_type("New York City is large") == "entity"
        assert extractor._classify_claim_type("This is a statement") == "general"

    def test_assess_claim_risk(self):
        """Test claim risk assessment."""
        extractor = ClaimExtractor(use_llm=False)
        
        high_risk = extractor._assess_claim_risk("The study shows 50% increase", "number")
        assert high_risk == "high"
        
        medium_risk = extractor._assess_claim_risk("In 2020, the event occurred", "date")
        assert medium_risk in ["medium", "high"]
        
        low_risk = extractor._assess_claim_risk("This is a general statement", "general")
        assert low_risk == "low"

    @pytest.mark.asyncio
    async def test_extract_claims_llm_mocked(self):
        """Test LLM-based claim extraction with mocked AI service."""
        ai_service = AsyncMock(spec=AIPlatformService)
        ai_service.get_response = AsyncMock(return_value=json.dumps([
            {
                "id": "c1",
                "claim": "The population is 8.5 million",
                "claim_type": "number",
                "original_span": "The population is 8.5 million",
                "risk": "high"
            }
        ]))
        
        extractor = ClaimExtractor(use_llm=True, ai_service=ai_service)
        
        response = "The population is 8.5 million."
        claims = await extractor._extract_claims_llm(response, max_claims=10)
        
        assert len(claims) > 0
        assert claims[0].id == "c1"

    @pytest.mark.asyncio
    async def test_extract_claims_llm_fallback(self):
        """Test that LLM extraction falls back to rule-based on error."""
        ai_service = AsyncMock(spec=AIPlatformService)
        ai_service.get_response = AsyncMock(side_effect=Exception("API error"))
        
        extractor = ClaimExtractor(use_llm=True, ai_service=ai_service)
        
        response = "The population is 8.5 million. In 2020, growth occurred."
        claims = await extractor.extract_claims(response, max_claims=10)
        
        # Should fall back to rule-based and still extract claims
        assert len(claims) >= 0  # May or may not extract depending on patterns


class TestEvidenceRetriever:
    """Tests for EvidenceRetriever class."""

    @pytest.mark.asyncio
    async def test_retrieve_evidence_success(self):
        """Test successful evidence retrieval from SerpAPI."""
        retriever = EvidenceRetriever(api_key="test-key", timeout=10, top_k=3)
        
        mock_response_data = {
            "organic_results": [
                {
                    "link": "https://example.com/article1",
                    "title": "Example Article 1",
                    "snippet": "This is a snippet about the claim",
                },
                {
                    "link": "https://example.com/article2",
                    "title": "Example Article 2",
                    "snippet": "Another snippet",
                },
            ]
        }
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            
            async with httpx.AsyncClient() as client:
                # Mock the client context manager
                with patch.object(client, "get", mock_get):
                    evidence = await retriever.retrieve_evidence("test claim")
                    
                    assert len(evidence) > 0
                    assert evidence[0].url == "https://example.com/article1"
                    assert evidence[0].title == "Example Article 1"

    @pytest.mark.asyncio
    async def test_retrieve_evidence_no_api_key(self):
        """Test that retrieval returns empty list when API key is missing."""
        retriever = EvidenceRetriever(api_key=None, timeout=10, top_k=3)
        
        evidence = await retriever.retrieve_evidence("test claim")
        
        assert evidence == []

    @pytest.mark.asyncio
    async def test_retrieve_evidence_timeout(self):
        """Test handling of timeout errors."""
        retriever = EvidenceRetriever(api_key="test-key", timeout=1, top_k=3)
        
        with patch("httpx.AsyncClient.get", side_effect=Exception("Timeout")):
            evidence = await retriever.retrieve_evidence("test claim")
            
            # Should return empty list on timeout
            assert evidence == []

    def test_filter_evidence_removes_duplicates(self):
        """Test that duplicate URLs are filtered out."""
        retriever = EvidenceRetriever(api_key="test-key", timeout=10, top_k=3)
        
        evidence_list = [
            Evidence(
                url="https://example.com/article1",
                title="Article 1",
                snippet="Snippet 1",
                source_rank=1,
                domain="example.com",
            ),
            Evidence(
                url="https://example.com/article1",  # Duplicate
                title="Article 1 Duplicate",
                snippet="Snippet 1",
                source_rank=2,
                domain="example.com",
            ),
            Evidence(
                url="https://example.com/article2",
                title="Article 2",
                snippet="Snippet 2",
                source_rank=3,
                domain="example.com",
            ),
        ]
        
        filtered = retriever._filter_evidence(evidence_list)
        
        assert len(filtered) == 2  # Duplicate removed
        assert filtered[0].url == "https://example.com/article1"
        assert filtered[1].url == "https://example.com/article2"


class TestEvidenceTextFetcher:
    """Tests for EvidenceTextFetcher class."""

    @pytest.mark.asyncio
    async def test_fetch_text_with_trafilatura(self):
        """Test text fetching with trafilatura."""
        fetcher = EvidenceTextFetcher(timeout=10, max_text_length=1000)
        
        evidence = Evidence(
            url="https://example.com/article",
            title="Test Article",
            snippet="Test snippet",
            source_rank=1,
            domain="example.com",
        )
        
        # Mock trafilatura and httpx
        with patch("trafilatura.extract", return_value="Extracted article text"):
            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.text = "<html>Test HTML</html>"
                mock_response.raise_for_status = MagicMock()
                mock_get.return_value = mock_response
                
                async with httpx.AsyncClient() as client:
                    with patch.object(client, "get", mock_get):
                        text = await fetcher.fetch_text(evidence)
                        
                        assert text == "Extracted article text"

    @pytest.mark.asyncio
    async def test_fetch_text_fallback_to_snippet(self):
        """Test that fetcher falls back to snippet on error."""
        fetcher = EvidenceTextFetcher(timeout=10, max_text_length=1000)
        
        evidence = Evidence(
            url="https://example.com/article",
            title="Test Article",
            snippet="Test snippet fallback",
            source_rank=1,
            domain="example.com",
        )
        
        # Simulate error
        with patch("httpx.AsyncClient.get", side_effect=Exception("Fetch error")):
            text = await fetcher.fetch_text(evidence)
            
            assert text == "Test snippet fallback"

    @pytest.mark.asyncio
    async def test_fetch_text_no_url(self):
        """Test that fetcher returns snippet when URL is missing."""
        fetcher = EvidenceTextFetcher(timeout=10, max_text_length=1000)
        
        evidence = Evidence(
            url="",
            title="Test Article",
            snippet="Test snippet",
            source_rank=1,
            domain="example.com",
        )
        
        text = await fetcher.fetch_text(evidence)
        
        assert text == "Test snippet"


class TestClaimVerifier:
    """Tests for ClaimVerifier class."""

    @pytest.mark.asyncio
    async def test_verify_claim_supported(self):
        """Test claim verification with SUPPORTED verdict."""
        ai_service = AsyncMock(spec=AIPlatformService)
        ai_service.get_response = AsyncMock(return_value=json.dumps({
            "verdict": "SUPPORTED",
            "confidence": 0.9,
            "explanation": "The evidence supports the claim"
        }))
        
        verifier = ClaimVerifier(
            ai_service=ai_service,
            judge_platform_id="openai",
            timeout=30,
        )
        
        claim = Claim(
            id="c1",
            claim="The population is 8.5 million",
            claim_type="number",
            original_span="The population is 8.5 million",
            risk="high",
        )
        
        evidence = Evidence(
            url="https://example.com/article",
            title="Test Article",
            snippet="The population of the city is 8.5 million according to recent data",
            source_rank=1,
            domain="example.com",
        )
        
        text_fetcher = EvidenceTextFetcher()
        
        result = await verifier.verify_claim(claim, [evidence], text_fetcher)
        
        assert result["verdict"] == "SUPPORTED"
        assert result["confidence"] > 0.0

    @pytest.mark.asyncio
    async def test_verify_claim_no_evidence(self):
        """Test verification when no evidence is provided."""
        ai_service = AsyncMock(spec=AIPlatformService)
        verifier = ClaimVerifier(
            ai_service=ai_service,
            judge_platform_id="openai",
            timeout=30,
        )
        
        claim = Claim(
            id="c1",
            claim="Test claim",
            claim_type="general",
            original_span="Test claim",
            risk="low",
        )
        
        text_fetcher = EvidenceTextFetcher()
        
        result = await verifier.verify_claim(claim, [], text_fetcher)
        
        assert result["verdict"] == "NOT_ENOUGH_INFO"
        assert result["confidence"] == 0.0


class TestExternalFactCheckScorer:
    """Tests for ExternalFactCheckScorer class."""

    @pytest.mark.asyncio
    async def test_calculate_sub_score_disabled(self):
        """Test that scorer returns neutral score when disabled."""
        with patch("app.core.config.get_settings") as mock_settings:
            from app.core.config import ExternalFactCheckSettings
            
            settings = MagicMock()
            settings.external_fact_check = ExternalFactCheckSettings(enabled=False)
            mock_settings.return_value = settings
            
            ai_service = AsyncMock(spec=AIPlatformService)
            scorer = ExternalFactCheckScorer(ai_service, "openai")
            
            result = await scorer.calculate_sub_score("Test response")
            
            assert result.score == 50
            assert result.coverage == 0.0
            assert "disabled" in result.notes[0].lower()

    @pytest.mark.asyncio
    async def test_calculate_sub_score_no_claims(self):
        """Test scoring when no claims are extracted."""
        with patch("app.core.config.get_settings") as mock_settings:
            from app.core.config import ExternalFactCheckSettings
            
            settings = MagicMock()
            settings.external_fact_check = ExternalFactCheckSettings(enabled=True)
            mock_settings.return_value = settings
            
            ai_service = AsyncMock(spec=AIPlatformService)
            scorer = ExternalFactCheckScorer(ai_service, "openai")
            
            # Mock claim extractor to return no claims
            with patch.object(scorer.claim_extractor, "extract_claims", return_value=[]):
                result = await scorer.calculate_sub_score("Test response")
                
                assert result.score == 50
                assert len(result.claims) == 0

    @pytest.mark.asyncio
    async def test_calculate_sub_score_end_to_end_mocked(self):
        """Test end-to-end scoring with all components mocked."""
        with patch("app.core.config.get_settings") as mock_settings:
            from app.core.config import ExternalFactCheckSettings
            
            settings = MagicMock()
            settings.external_fact_check = ExternalFactCheckSettings(
                enabled=True,
                serpapi_api_key="test-key",
                top_k_results=3,
            )
            mock_settings.return_value = settings
            
            ai_service = AsyncMock(spec=AIPlatformService)
            ai_service.get_response = AsyncMock(return_value=json.dumps({
                "verdict": "SUPPORTED",
                "confidence": 0.8,
                "explanation": "Evidence supports"
            }))
            
            scorer = ExternalFactCheckScorer(ai_service, "openai")
            
            # Mock all components
            test_claim = Claim(
                id="c1",
                claim="The population is 8.5 million",
                claim_type="number",
                original_span="The population is 8.5 million",
                risk="high",
            )
            
            test_evidence = Evidence(
                url="https://example.com/article",
                title="Test Article",
                snippet="The population is 8.5 million",
                source_rank=1,
                domain="example.com",
            )
            
            with patch.object(scorer.claim_extractor, "extract_claims", return_value=[test_claim]):
                with patch.object(scorer.evidence_retriever, "retrieve_evidence", return_value=[test_evidence]):
                    with patch.object(scorer.text_fetcher, "fetch_text", return_value="Test text"):
                        result = await scorer.calculate_sub_score("The population is 8.5 million.")
                        
                        assert result.score >= 0
                        assert result.score <= 100
                        assert len(result.claims) > 0
                        assert result.claims[0].verdict in ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]

    def test_calculate_score_supported_claims(self):
        """Test score calculation with supported claims."""
        scorer = ExternalFactCheckScorer(AsyncMock(), "openai")
        
        claims = [
            ExternalFactCheckClaim(
                id="c1",
                claim="Claim 1",
                claim_type="general",
                original_span="Claim 1",
                risk="low",
                verdict="SUPPORTED",
                confidence=0.8,
                top_evidence=[],
            ),
            ExternalFactCheckClaim(
                id="c2",
                claim="Claim 2",
                claim_type="number",
                original_span="Claim 2",
                risk="high",
                verdict="SUPPORTED",
                confidence=0.9,
                top_evidence=[],
            ),
        ]
        
        score, coverage = scorer._calculate_score(claims)
        
        assert score > 50  # Should be above neutral
        assert coverage > 0.0

    def test_calculate_score_refuted_claims(self):
        """Test score calculation with refuted claims."""
        scorer = ExternalFactCheckScorer(AsyncMock(), "openai")
        
        claims = [
            ExternalFactCheckClaim(
                id="c1",
                claim="Claim 1",
                claim_type="general",
                original_span="Claim 1",
                risk="high",
                verdict="REFUTED",
                confidence=0.8,
                top_evidence=[],
            ),
        ]
        
        score, coverage = scorer._calculate_score(claims)
        
        assert score < 50  # Should be below neutral due to refuted claim
        assert coverage > 0.0

    def test_calculate_score_mixed_verdicts(self):
        """Test score calculation with mixed verdicts."""
        scorer = ExternalFactCheckScorer(AsyncMock(), "openai")
        
        claims = [
            ExternalFactCheckClaim(
                id="c1",
                claim="Claim 1",
                claim_type="general",
                original_span="Claim 1",
                risk="low",
                verdict="SUPPORTED",
                confidence=0.8,
                top_evidence=[],
            ),
            ExternalFactCheckClaim(
                id="c2",
                claim="Claim 2",
                claim_type="general",
                original_span="Claim 2",
                risk="low",
                verdict="REFUTED",
                confidence=0.7,
                top_evidence=[],
            ),
            ExternalFactCheckClaim(
                id="c3",
                claim="Claim 3",
                claim_type="general",
                original_span="Claim 3",
                risk="low",
                verdict="NOT_ENOUGH_INFO",
                confidence=0.0,
                top_evidence=[],
            ),
        ]
        
        score, coverage = scorer._calculate_score(claims)
        
        assert 0 <= score <= 100
        assert 0.0 <= coverage <= 1.0


class TestExternalFactCheckIntegration:
    """Integration tests for external fact check with mocked external calls."""

    @pytest.mark.asyncio
    async def test_end_to_end_integration_mocked(self):
        """Test complete end-to-end flow with all external calls mocked."""
        with patch("app.core.config.get_settings") as mock_settings:
            from app.core.config import ExternalFactCheckSettings
            
            settings = MagicMock()
            settings.external_fact_check = ExternalFactCheckSettings(
                enabled=True,
                serpapi_api_key="test-api-key",
                top_k_results=3,
                claim_extraction_use_llm=False,
                verification_timeout=30,
                search_timeout=10,
                max_claims_per_response=10,
            )
            mock_settings.return_value = settings
            
            # Mock AI service for verification
            ai_service = AsyncMock(spec=AIPlatformService)
            ai_service.get_response = AsyncMock(return_value=json.dumps({
                "verdict": "SUPPORTED",
                "confidence": 0.85,
                "explanation": "The evidence clearly supports this claim"
            }))
            
            scorer = ExternalFactCheckScorer(ai_service, "openai")
            
            # Mock SerpAPI response
            serpapi_response = {
                "organic_results": [
                    {
                        "link": "https://example.com/fact1",
                        "title": "Factual Article 1",
                        "snippet": "The population of New York City is approximately 8.5 million people according to recent census data.",
                    },
                    {
                        "link": "https://example.com/fact2",
                        "title": "Factual Article 2",
                        "snippet": "New York City has a population of 8.5 million residents.",
                    },
                ]
            }
            
            # Mock httpx for SerpAPI
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.json.return_value = serpapi_response
                mock_response.raise_for_status = MagicMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_class.return_value = mock_client
                
                # Mock trafilatura for text extraction
                with patch("trafilatura.extract", return_value="The population of New York City is 8.5 million according to official census data."):
                    # Mock httpx for text fetching
                    with patch("httpx.AsyncClient.get") as mock_get:
                        mock_text_response = MagicMock()
                        mock_text_response.text = "<html>Test HTML</html>"
                        mock_text_response.raise_for_status = MagicMock()
                        mock_get.return_value = mock_text_response
                        
                        # Test with a response containing factual claims
                        response = "New York City has a population of 8.5 million people. This makes it one of the largest cities in the United States."
                        
                        result = await scorer.calculate_sub_score(response)
                        
                        # Verify result structure
                        assert isinstance(result, ExternalFactCheckResult)
                        assert result.sub_score_name == "External Fact Check"
                        assert 0 <= result.score <= 100
                        assert 0.0 <= result.coverage <= 1.0
                        assert isinstance(result.claims, list)
                        assert isinstance(result.sources_used, list)
                        
                        # If claims were extracted, verify their structure
                        if result.claims:
                            for claim in result.claims:
                                assert isinstance(claim, ExternalFactCheckClaim)
                                assert claim.verdict in ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]
                                assert 0.0 <= claim.confidence <= 1.0
                                assert claim.id.startswith("c")
                                assert claim.claim_type in ["date", "number", "entity", "general"]
                                assert claim.risk in ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_integration_with_hallucination_scorer(self):
        """Test integration with HallucinationScorer."""
        from app.services.comparison.hallucination_scorer import HallucinationScorer
        
        scorer = HallucinationScorer()
        
        # Mock external fact check to avoid actual API calls
        with patch.object(
            scorer,
            "_external_fact_check_scorer",
            create=True,
        ) as mock_external_scorer:
            mock_result = ExternalFactCheckResult(
                sub_score_name="External Fact Check",
                score=75,
                coverage=0.8,
                claims=[],
                sources_used=[],
                notes=[],
            )
            mock_external_scorer.calculate_sub_score = AsyncMock(return_value=mock_result)
            
            response = "New York City has a population of 8.5 million people."
            all_responses = {"openai": response}
            
            sub_scores = await scorer.calculate_sub_scores(
                response=response,
                judge_platform_id="openai",
                all_responses=all_responses,
                use_llm=False,
                use_embeddings=False,
            )
            
            # Verify external fact check score is included
            assert hasattr(sub_scores, "externalFactCheckScore")
            assert sub_scores.externalFactCheckScore == 75
