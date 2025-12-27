"""Service for calculating compliance scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import (
    ComplianceSubScore,
    ComplianceDetails,
    ComplianceRule,
    ComplianceSummary,
)
from app.services.comparison.compliance.comprehensive_compliance_analyzer import (
    ComprehensiveComplianceAnalyzer,
)


class ComplianceScorer:
    """Service for calculating compliance scores and sub-scores using comprehensive LLM analysis."""

    def __init__(self):
        """Initialize compliance scorer with comprehensive analyzer."""
        self.compliance_analyzer = ComprehensiveComplianceAnalyzer()

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = True,  # Default to True - LLM is required for comprehensive analysis
    ) -> ComplianceSubScore:
        """Calculate comprehensive compliance sub-scores using LLM analysis.
        
        Uses LLM semantic analysis to evaluate compliance against 6 major regulatory standards:
        - GDPR
        - EU AI Act
        - Responsible AI
        - ISO/IEC 42001
        - HIPAA
        - SOC-2 AI
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM (must be True for comprehensive analysis)
        
        Returns:
            ComplianceSubScore with:
            - checksUrlsExist: [DEPRECATED] Legacy field, always False
            - verifiesPapersExist: [DEPRECATED] Legacy field, always False
            - detectsFakeCitations: [DEPRECATED] Legacy field, always False
            - confirmsLegalReferences: [DEPRECATED] Legacy field, always False
            - complianceDetails: Detailed regulatory compliance analysis
        """
        # Get comprehensive compliance analysis
        compliance_details = None
        try:
            analysis_result = await self.compliance_analyzer.analyze_compliance(
                response, judge_platform_id, use_llm=use_llm
            )
            
            # Convert rules to schema format
            rules = [
                ComplianceRule(
                    module=rule.get("module", ""),
                    rule_name=rule.get("rule_name", ""),
                    status=rule.get("status", "passed"),
                    severity=rule.get("severity", "low"),
                    text=rule.get("text", ""),
                    explanation=rule.get("explanation", ""),
                )
                for rule in analysis_result.get("rules", [])
            ]
            
            # Create summary
            summary_data = analysis_result.get("summary", {})
            summary = ComplianceSummary(
                total_rules=summary_data.get("total_rules", 0),
                passed_rules=summary_data.get("passed_rules", 0),
                violated_rules=summary_data.get("violated_rules", 0),
                high_risk_violations=summary_data.get("high_risk_violations", 0),
            )
            
            # Get scores
            overall_score = analysis_result.get("overall_score", 6)
            module_scores = analysis_result.get("module_scores", {})
            
            # Convert module_scores dict values to int
            module_scores_int = {
                k: int(v) if isinstance(v, (int, float)) else 6
                for k, v in module_scores.items()
            }
            
            # Use overall_score as the main score
            main_score = int(round(overall_score))
            
            # Create detailed results
            compliance_details = ComplianceDetails(
                sub_score_name="Compliance Score",
                score=main_score,
                module_scores=module_scores_int,
                rules=rules,
                summary=summary,
                explanation=analysis_result.get("explanation", ""),
            )
            
        except Exception as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "compliance_analysis_failed",
                error=str(e),
                exc_info=True,
            )
            # Use default values on error
            compliance_details = None
        
        # Return ComplianceSubScore with legacy fields set to False for backward compatibility
        return ComplianceSubScore(
            checksUrlsExist=False,  # Legacy field, deprecated
            verifiesPapersExist=False,  # Legacy field, deprecated
            detectsFakeCitations=False,  # Legacy field, deprecated
            confirmsLegalReferences=False,  # Legacy field, deprecated
            complianceDetails=compliance_details,
        )

    # Legacy method names for backward compatibility
    async def calculate_checks_urls_exist(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if URLs existence is checked (Yes/No).
        
        [DEPRECATED] Legacy method for backward compatibility.
        This method always returns False as the old citation-based compliance checks
        have been replaced with comprehensive regulatory compliance analysis.
        Use calculate_sub_scores() for new compliance analysis.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Always returns False (deprecated functionality)
        """
        return False

    async def calculate_verifies_papers_exist(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if papers existence is verified (Yes/No).
        
        [DEPRECATED] Legacy method for backward compatibility.
        This method always returns False as the old citation-based compliance checks
        have been replaced with comprehensive regulatory compliance analysis.
        Use calculate_sub_scores() for new compliance analysis.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Always returns False (deprecated functionality)
        """
        return False

    async def calculate_detects_fake_citations(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if fake citations are detected (Yes/No).
        
        [DEPRECATED] Legacy method for backward compatibility.
        This method always returns False as the old citation-based compliance checks
        have been replaced with comprehensive regulatory compliance analysis.
        Use calculate_sub_scores() for new compliance analysis.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Always returns False (deprecated functionality)
        """
        return False

    async def calculate_confirms_legal_references(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if legal references are confirmed (Yes/No).
        
        [DEPRECATED] Legacy method for backward compatibility.
        This method always returns False as the old citation-based compliance checks
        have been replaced with comprehensive regulatory compliance analysis.
        Use calculate_sub_scores() for new compliance analysis.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Always returns False (deprecated functionality)
        """
        return False

