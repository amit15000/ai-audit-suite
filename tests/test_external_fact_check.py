"""Tests for current external fact check implementation."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.schemas import ExternalFactCheckResult
from app.services.comparison.hallucination.external_fact_check import (
    Claim,
    ClaimEnricher,
    ClaimExtractor,
    ExternalFactCheckScorer,
    LLMFactChecker,
)


class TestClaimExtractor:
    @pytest.mark.asyncio
    async def test_extract_claims_llm_success(self):
        with patch("app.services.comparison.hallucination.external_fact_check._call_openai") as mock_call:
            mock_call.return_value = json.dumps([
                {"id": "c1", "claim": "NYC population is about 8.5 million", "original_span": "NYC population is about 8.5 million."}
            ])
            claims = await ClaimExtractor(use_llm=True).extract_claims("NYC population is about 8.5 million.", max_claims=5)
            assert len(claims) == 1
            assert claims[0].id == "c1"

    @pytest.mark.asyncio
    async def test_extract_claims_llm_failure_returns_empty(self):
        with patch("app.services.comparison.hallucination.external_fact_check._call_openai", side_effect=Exception("boom")):
            claims = await ClaimExtractor(use_llm=True).extract_claims("Any text", max_claims=5)
            assert claims == []


class TestClaimEnricher:
    @pytest.mark.asyncio
    async def test_enrich_claims_uses_llm_output(self):
        claims = [Claim(id="c1", claim="It has 8.5 million people", original_span="It has 8.5 million people")]
        with patch("app.services.comparison.hallucination.external_fact_check._call_openai") as mock_call:
            mock_call.return_value = json.dumps([
                {"id": "c1", "claim": "New York City has 8.5 million people", "original_span": "It has 8.5 million people"}
            ])
            enriched = await ClaimEnricher().enrich_claims(claims, "New York City is large. It has 8.5 million people.")
            assert enriched[0].claim == "New York City has 8.5 million people"


class TestLLMFactChecker:
    @pytest.mark.asyncio
    async def test_verify_claim_true(self):
        claim = Claim(id="c1", claim="Water boils at 100C at sea level", original_span="Water boils at 100C")
        with patch("app.services.comparison.hallucination.external_fact_check._call_openai") as mock_call:
            mock_call.return_value = json.dumps(
                {
                    "is_true": True,
                    "explanation": "Standard atmospheric boiling point.",
                    "sources_used": ["https://en.wikipedia.org/wiki/Boiling_point"],
                }
            )
            result = await LLMFactChecker(timeout=5).verify_claim(claim)
            assert result["is_true"] is True
            assert result["sources_used"]

    @pytest.mark.asyncio
    async def test_verify_claim_failure_defaults_false(self):
        claim = Claim(id="c1", claim="Some claim", original_span="Some claim")
        with patch("app.services.comparison.hallucination.external_fact_check._call_openai", side_effect=Exception("down")):
            result = await LLMFactChecker(timeout=5).verify_claim(claim)
            assert result["is_true"] is False
            assert result["sources_used"] == []


class TestExternalFactCheckScorer:
    @pytest.mark.asyncio
    async def test_calculate_sub_score_disabled(self):
        mock_settings = MagicMock()
        mock_settings.external_fact_check.enabled = False
        with patch("app.services.comparison.hallucination.external_fact_check.get_settings", return_value=mock_settings):
            result = await ExternalFactCheckScorer().calculate_sub_score("Test response")
            assert isinstance(result, ExternalFactCheckResult)
            assert result.score == 50
            assert result.coverage == 0.0

    @pytest.mark.asyncio
    async def test_calculate_sub_score_no_claims(self):
        mock_settings = MagicMock()
        mock_settings.external_fact_check.enabled = True
        mock_settings.external_fact_check.claim_extraction_use_llm = True
        mock_settings.external_fact_check.verification_timeout = 5
        mock_settings.external_fact_check.max_claims_per_response = 5

        with patch("app.services.comparison.hallucination.external_fact_check.get_settings", return_value=mock_settings):
            scorer = ExternalFactCheckScorer()
            with patch.object(scorer.claim_extractor, "extract_claims", AsyncMock(return_value=[])):
                result = await scorer.calculate_sub_score("No factual statements here.")
                assert result.score == 50
                assert result.claims == []

    @pytest.mark.asyncio
    async def test_calculate_sub_score_supported_claim(self):
        mock_settings = MagicMock()
        mock_settings.external_fact_check.enabled = True
        mock_settings.external_fact_check.claim_extraction_use_llm = True
        mock_settings.external_fact_check.verification_timeout = 5
        mock_settings.external_fact_check.max_claims_per_response = 5

        with patch("app.services.comparison.hallucination.external_fact_check.get_settings", return_value=mock_settings):
            scorer = ExternalFactCheckScorer()
            claim = Claim(id="c1", claim="Earth is round", original_span="Earth is round")
            with patch.object(scorer.claim_extractor, "extract_claims", AsyncMock(return_value=[claim])):
                with patch.object(scorer.claim_enricher, "enrich_claims", AsyncMock(return_value=[claim])):
                    with patch.object(
                        scorer.fact_checker,
                        "verify_claim",
                        AsyncMock(
                            return_value={
                                "is_true": True,
                                "explanation": "Well-established fact.",
                                "sources_used": ["https://en.wikipedia.org/wiki/Spherical_Earth"],
                            }
                        ),
                    ):
                        result = await scorer.calculate_sub_score("Earth is round.")
                        assert result.score == 100
                        assert result.coverage == 1.0
                        assert len(result.claims) == 1
