"""Service for calculating compliance scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import ComplianceSubScore
from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.compliance import (
    ChecksUrlsExistScorer,
    VerifiesPapersExistScorer,
    DetectsFakeCitationsScorer,
    ConfirmsLegalReferencesScorer,
)


class ComplianceScorer:
    """Service for calculating compliance scores and sub-scores."""

    def __init__(self):
        """Initialize compliance scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        self.citation_verifier = CitationVerifier()
        
        # Initialize sub-score calculators
        self.checks_urls_exist_scorer = ChecksUrlsExistScorer(
            self.citation_verifier, self.ai_service
        )
        self.verifies_papers_exist_scorer = VerifiesPapersExistScorer(
            self.citation_verifier, self.ai_service
        )
        self.detects_fake_citations_scorer = DetectsFakeCitationsScorer(
            self.citation_verifier, self.ai_service
        )
        self.confirms_legal_references_scorer = ConfirmsLegalReferencesScorer(
            self.citation_verifier, self.ai_service
        )

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> ComplianceSubScore:
        """Calculate the 4 compliance sub-scores.
        
        Uses citation verification to check compliance with various standards.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            ComplianceSubScore with:
            - checksUrlsExist: Whether URLs existence is checked (Yes/No)
            - verifiesPapersExist: Whether papers existence is verified (Yes/No)
            - detectsFakeCitations: Whether fake citations are detected (Yes/No)
            - confirmsLegalReferences: Whether legal references are confirmed (Yes/No)
        """
        # Calculate each sub-score
        checks_urls = await self.checks_urls_exist_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        verifies_papers = await self.verifies_papers_exist_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        detects_fake = await self.detects_fake_citations_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        confirms_legal = await self.confirms_legal_references_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return ComplianceSubScore(
            checksUrlsExist=checks_urls,
            verifiesPapersExist=verifies_papers,
            detectsFakeCitations=detects_fake,
            confirmsLegalReferences=confirms_legal,
        )

    # Legacy method names for backward compatibility
    async def calculate_checks_urls_exist(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if URLs existence is checked (Yes/No).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if URLs existence is checked, False otherwise
        """
        return await self.checks_urls_exist_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_verifies_papers_exist(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if papers existence is verified (Yes/No).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if papers existence is verified, False otherwise
        """
        return await self.verifies_papers_exist_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_detects_fake_citations(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if fake citations are detected (Yes/No).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if fake citations are detected, False otherwise
        """
        return await self.detects_fake_citations_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_confirms_legal_references(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if legal references are confirmed (Yes/No).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if legal references are confirmed, False otherwise
        """
        return await self.confirms_legal_references_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

