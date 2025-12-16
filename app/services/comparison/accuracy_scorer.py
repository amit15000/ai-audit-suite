"""Service for calculating accuracy scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import AccuracySubScore
from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.accuracy import (
    GoogleBingWikipediaScorer,
    VerifiedDatabasesScorer,
    InternalCompanyDocsScorer,
)


class AccuracyScorer:
    """Service for calculating accuracy scores and sub-scores."""

    def __init__(self):
        """Initialize accuracy scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        self.citation_verifier = CitationVerifier()
        
        # Initialize sub-score calculators
        self.google_bing_wikipedia_scorer = GoogleBingWikipediaScorer(
            self.citation_verifier, self.ai_service
        )
        self.verified_databases_scorer = VerifiedDatabasesScorer(self.ai_service)
        self.internal_company_docs_scorer = InternalCompanyDocsScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> AccuracySubScore:
        """Calculate the 3 accuracy sub-scores.
        
        Uses rule-based methods first (fast, deterministic), optionally enhanced with LLM.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            AccuracySubScore with scores for:
            - googleBingWikipediaScore: Google/Bing search Wikipedia verification
            - verifiedDatabasesScore: Verified databases (medical, legal, financial, HR)
            - internalCompanyDocsScore: Internal company docs verification
        """
        # Calculate each sub-score (rule-based by default, LLM-enhanced if requested)
        google_bing_wikipedia_score = await self.google_bing_wikipedia_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        verified_databases_score = await self.verified_databases_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        internal_company_docs_score = await self.internal_company_docs_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return AccuracySubScore(
            googleBingWikipediaScore=google_bing_wikipedia_score,
            verifiedDatabasesScore=verified_databases_score,
            internalCompanyDocsScore=internal_company_docs_score,
        )

    # Legacy method names for backward compatibility
    async def calculate_google_bing_wikipedia_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for Google/Bing search Wikipedia verification (0-10).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Score between 0-10
        """
        return await self.google_bing_wikipedia_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_verified_databases_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for verified databases (medical, legal, financial, HR) (0-10).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Score between 0-10
        """
        return await self.verified_databases_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_internal_company_docs_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for internal company docs verification (0-10).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Score between 0-10
        """
        return await self.internal_company_docs_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

