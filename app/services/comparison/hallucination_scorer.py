"""Service for calculating hallucination scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import HallucinationSubScore
from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.hallucination import (
    FactCheckingScorer,
    FabricatedCitationsScorer,
    ContradictoryInfoScorer,
    MultiLLMComparisonScorer,
)


class HallucinationScorer:
    """Service for calculating hallucination scores and sub-scores."""

    def __init__(self):
        """Initialize hallucination scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        self.citation_verifier = CitationVerifier()
        
        # Initialize sub-score calculators
        self.fact_checking_scorer = FactCheckingScorer(
            self.citation_verifier, self.ai_service
        )
        self.fabricated_citations_scorer = FabricatedCitationsScorer(
            self.citation_verifier, self.ai_service
        )
        self.contradictory_info_scorer = ContradictoryInfoScorer(self.ai_service)
        self.multi_llm_comparison_scorer = MultiLLMComparisonScorer()

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        all_responses: dict[str, str],
        use_llm: bool = False,
        use_embeddings: bool = False,
    ) -> HallucinationSubScore:
        """Calculate the 4 hallucination sub-scores.
        
        Uses rule-based methods first (fast, deterministic), optionally enhanced with LLM/embeddings.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            all_responses: Dictionary of all LLM responses for comparison
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            use_embeddings: Whether to use embeddings for semantic similarity (default: False)
        
        Returns:
            HallucinationSubScore with scores for:
            - factCheckingScore: Checking facts against external sources
            - fabricatedCitationsScore: Detecting fabricated citations
            - contradictoryInfoScore: Identifying contradictory information
            - multiLLMComparisonScore: Comparing against multiple LLMs
        """
        # Calculate each sub-score (rule-based by default, LLM-enhanced if requested)
        fact_checking_score = await self.fact_checking_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        fabricated_citations_score = await self.fabricated_citations_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        contradictory_info_score = await self.contradictory_info_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        multi_llm_comparison_score = await self.multi_llm_comparison_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )
        
        return HallucinationSubScore(
            factCheckingScore=fact_checking_score,
            fabricatedCitationsScore=fabricated_citations_score,
            contradictoryInfoScore=contradictory_info_score,
            multiLLMComparisonScore=multi_llm_comparison_score,
        )

    # Legacy method names for backward compatibility
    async def calculate_fact_checking_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for fact-checking against external sources (0-10).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Score between 0-10
        """
        return await self.fact_checking_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_fabricated_citations_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for detecting fabricated citations (0-10).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced verification (default: False)
            
        Returns:
            Score between 0-10
        """
        return await self.fabricated_citations_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_contradictory_info_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for identifying contradictory information (0-10).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced analysis (default: False)
            
        Returns:
            Score between 0-10
        """
        return await self.contradictory_info_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_multi_llm_comparison_score(
        self, response: str, all_responses: dict[str, str], use_embeddings: bool = False
    ) -> int:
        """Calculate score by comparing response against multiple LLM responses (0-10).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings for better comparison (default: False)
            
        Returns:
            Score between 0-10
        """
        return await self.multi_llm_comparison_scorer.calculate_score(
            response, all_responses, use_embeddings=use_embeddings
        )
