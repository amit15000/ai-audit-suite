"""Service for calculating hallucination scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import (
    HallucinationSubScore,
    FabricatedCitationsDetails,
    ContradictoryInfoDetails,
    ContradictoryInfoContradictionPair,
)
from app.services.comparison.citation_verifier import CitationVerifier
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.hallucination import (
    FactCheckingScorer,
    FabricatedCitationsScorer,
    ContradictoryInfoScorer,
    MultiLLMComparisonScorer,
)
from app.services.comparison.hallucination.external_fact_check import ExternalFactCheckScorer


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
        self.contradictory_info_scorer = ContradictoryInfoScorer()
        self.multi_llm_comparison_scorer = MultiLLMComparisonScorer()  # No longer needs ai_service
        # External fact check scorer will be initialized lazily with judge_platform_id
        self._external_fact_check_scorer: ExternalFactCheckScorer | None = None

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        all_responses: dict[str, str],
        use_llm: bool = False,
        use_embeddings: bool = False,
        original_prompt: str | None = None,
        target_platform_id: str | None = None,
    ) -> HallucinationSubScore:
        """Calculate the 4 hallucination sub-scores.
        
        Uses rule-based methods first (fast, deterministic), optionally enhanced with LLM/embeddings.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            all_responses: Dictionary of all LLM responses for comparison
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            use_embeddings: Whether to use embeddings for semantic similarity (default: False)
            original_prompt: Original prompt that generated the response (for multi-LLM comparison)
            target_platform_id: Platform ID that generated the response (for multi-LLM comparison)
        
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
        # Contradictory info requires LLM - always use LLM for this
        contradictory_info_score = await self.contradictory_info_scorer.calculate_score(
            response, judge_platform_id, use_llm=True  # Always use LLM for contradictory info
        )
        
        # Multi-LLM comparison: Use existing responses from all_responses if available, otherwise generate new ones
        multi_llm_comparison_score = 6  # Default neutral score
        multi_llm_comparison_details = None
        if original_prompt and target_platform_id:
            try:
                # Use existing responses from all_responses (if user already selected multiple platforms)
                multi_llm_comparison_score = await self.multi_llm_comparison_scorer.calculate_score(
                    response, original_prompt, target_platform_id, judge_platform_id, use_llm=True, all_responses=all_responses
                )
                # Get detailed comparison results
                detailed_comparison = await self.multi_llm_comparison_scorer.get_detailed_comparison(
                    response, original_prompt, target_platform_id, judge_platform_id, use_llm=True, all_responses=all_responses
                )
                from app.domain.schemas import (
                    MultiLLMComparisonDetails,
                    MultiLLMComparisonUniqueClaim,
                    MultiLLMComparisonContradictoryClaim,
                    MultiLLMComparisonConsensusClaim,
                )
                
                # Convert to schema format
                unique_claims = [
                    MultiLLMComparisonUniqueClaim(
                        claim=claim.get("claim", ""),
                        explanation=claim.get("explanation", ""),
                        severity=claim.get("severity", "medium"),
                    )
                    for claim in detailed_comparison.get("unique_claims", [])
                ]
                
                contradictory_claims = [
                    MultiLLMComparisonContradictoryClaim(
                        target_claim=claim.get("target_claim", ""),
                        consensus_claim=claim.get("consensus_claim", ""),
                        consensus_count=claim.get("consensus_count", 0),
                        explanation=claim.get("explanation", ""),
                        severity=claim.get("severity", "medium"),
                    )
                    for claim in detailed_comparison.get("contradictory_claims", [])
                ]
                
                consensus_claims = [
                    MultiLLMComparisonConsensusClaim(
                        claim=claim.get("claim", ""),
                        agreement_count=claim.get("agreement_count", 0),
                        total_responses=claim.get("total_responses", 0),
                    )
                    for claim in detailed_comparison.get("consensus_claims", [])
                ]
                
                multi_llm_comparison_details = MultiLLMComparisonDetails(
                    sub_score_name="Multi-LLM Comparison",
                    score=detailed_comparison["score"],
                    consensus_alignment=detailed_comparison.get("consensus_alignment", 50.0),
                    unique_claims_count=detailed_comparison.get("unique_claims_count", 0),
                    contradictory_claims_count=detailed_comparison.get("contradictory_claims_count", 0),
                    consensus_claims_count=detailed_comparison.get("consensus_claims_count", 0),
                    reference_llms_used=detailed_comparison.get("reference_llms_used", []),
                    unique_claims=unique_claims,
                    contradictory_claims=contradictory_claims,
                    consensus_claims=consensus_claims,
                    explanation=detailed_comparison.get("explanation", ""),
                )
            except Exception as e:
                import structlog
                logger = structlog.get_logger(__name__)
                logger.warning(
                    "multi_llm_comparison_calculation_failed",
                    error=str(e),
                    exc_info=True,
                )
                # Use default score on error
        
        # Calculate external fact check sub-score with details
        external_fact_check_score = 50  # Default neutral score
        external_fact_check_result = None
        try:
            if self._external_fact_check_scorer is None:
                self._external_fact_check_scorer = ExternalFactCheckScorer()
            
            external_fact_check_result = await self._external_fact_check_scorer.calculate_sub_score(
                response
            )
            external_fact_check_score = external_fact_check_result.score
        except Exception as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "external_fact_check_calculation_failed",
                error=str(e),
                exc_info=True,
            )
            # Use default score on error
        
        # Get fabricated citations details
        fabricated_citations_details = None
        try:
            fabricated_citations_report = await self.fabricated_citations_scorer.get_detailed_verification_report(
                response, judge_platform_id, use_llm=use_llm
            )
            fabricated_citations_details = FabricatedCitationsDetails(
                sub_score_name="Fabricated Citations",
                score=fabricated_citations_report["score"],
                total_citations=fabricated_citations_report["total_citations"],
                verified_count=fabricated_citations_report["verified_count"],
                fabricated_count=fabricated_citations_report["fabricated_count"],
                citations=fabricated_citations_report["citations"],
            )
        except Exception as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "fabricated_citations_details_failed",
                error=str(e),
                exc_info=True,
            )
        
        # Get contradictory information details
        contradictory_info_details = None
        try:
            contradictory_info_result = await self.contradictory_info_scorer.get_detailed_contradictions(
                response, judge_platform_id, use_llm=True  # Always use LLM
            )
            
            # Convert contradiction pairs to schema format
            contradiction_pairs = []
            for pair_data in contradictory_info_result.get("contradiction_pairs", []):
                contradiction_pairs.append(ContradictoryInfoContradictionPair(
                    statement_1=pair_data.get("statement_1", ""),
                    statement_2=pair_data.get("statement_2", ""),
                    type=pair_data.get("type", "factual"),
                    severity=pair_data.get("severity", "medium"),
                    semantic_reasoning=pair_data.get("semantic_reasoning", ""),
                ))
            
            contradictory_info_details = ContradictoryInfoDetails(
                sub_score_name="Contradictory Information",
                score=contradictory_info_result["score"],
                contradictions_found=contradictory_info_result["contradictions_found"],
                contradiction_pairs=contradiction_pairs,
                explanation=contradictory_info_result.get("explanation", ""),
            )
        except Exception as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "contradictory_info_details_failed",
                error=str(e),
                exc_info=True,
            )
        
        return HallucinationSubScore(
            factCheckingScore=fact_checking_score,
            fabricatedCitationsScore=fabricated_citations_score,
            contradictoryInfoScore=contradictory_info_score,
            multiLLMComparisonScore=multi_llm_comparison_score,
            externalFactCheckScore=external_fact_check_score,
            externalFactCheckDetails=external_fact_check_result,
            fabricatedCitationsDetails=fabricated_citations_details,
            contradictoryInfoDetails=contradictory_info_details,
            multiLLMComparisonDetails=multi_llm_comparison_details,
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
        # TODO: Implement new multi-LLM comparison score calculation
        return 6  # Placeholder until new implementation
