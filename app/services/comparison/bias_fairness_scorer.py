"""Service for calculating bias & fairness scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import (
    BiasFairnessSubScore,
    BiasFairnessDetails,
    BiasInstance,
    BiasSummary,
    FairnessInstance,
    FairnessIndicators,
)
from app.services.comparison.bias_fairness.comprehensive_bias_analyzer import ComprehensiveBiasAnalyzer


class BiasFairnessScorer:
    """Service for calculating bias & fairness scores and sub-scores using comprehensive LLM analysis."""

    def __init__(self):
        """Initialize bias & fairness scorer with comprehensive analyzer."""
        self.bias_analyzer = ComprehensiveBiasAnalyzer()

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = True,  # Default to True - LLM is required for comprehensive analysis
    ) -> BiasFairnessSubScore:
        """Calculate comprehensive bias & fairness sub-scores using LLM analysis.
        
        Uses LLM semantic analysis to detect all types of bias in a single comprehensive pass.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM (must be True for comprehensive analysis)
        
        Returns:
            BiasFairnessSubScore with:
            - genderBias: Whether gender bias is detected (Yes/No) - derived from analysis
            - racialBias: Whether racial bias is detected (Yes/No) - derived from analysis
            - religiousBias: Whether religious bias is detected (Yes/No) - derived from analysis
            - politicalBias: Whether political bias is detected (Yes/No) - derived from analysis
            - culturalInsensitivity: Whether cultural insensitivity is detected (Yes/No) - derived from analysis
            - biasFairnessDetails: Detailed analysis with all bias instances
        """
        # Get comprehensive bias analysis
        bias_details = None
        try:
            analysis_result = await self.bias_analyzer.analyze_bias(
                response, judge_platform_id, use_llm=use_llm
            )
            
            # Convert bias instances to schema format
            bias_instances = [
                BiasInstance(
                    type=instance.get("type", "other"),
                    severity=instance.get("severity", "medium"),
                    text=instance.get("text", ""),
                    explanation=instance.get("explanation", ""),
                    category=instance.get("category", ""),
                )
                for instance in analysis_result.get("bias_instances", [])
            ]
            
            # Convert fairness instances to schema format
            fairness_instances = [
                FairnessInstance(
                    type=instance.get("type", "inclusivity"),
                    strength=instance.get("strength", "medium"),
                    text=instance.get("text", ""),
                    explanation=instance.get("explanation", ""),
                )
                for instance in analysis_result.get("fairness_instances", [])
            ]
            
            # Create bias summary
            summary_data = analysis_result.get("bias_summary", {})
            bias_summary = BiasSummary(
                gender_bias_count=summary_data.get("gender_bias_count", 0),
                racial_bias_count=summary_data.get("racial_bias_count", 0),
                religious_bias_count=summary_data.get("religious_bias_count", 0),
                political_bias_count=summary_data.get("political_bias_count", 0),
                cultural_insensitivity_count=summary_data.get("cultural_insensitivity_count", 0),
                other_bias_count=summary_data.get("other_bias_count", 0),
                total_bias_count=summary_data.get("total_bias_count", 0),
            )
            
            # Create fairness indicators
            fairness_indicators_data = analysis_result.get("fairness_indicators", {})
            fairness_indicators = FairnessIndicators(
                inclusivity=fairness_indicators_data.get("inclusivity", False),
                balanced_representation=fairness_indicators_data.get("balanced_representation", False),
                equal_treatment=fairness_indicators_data.get("equal_treatment", False),
                cultural_sensitivity=fairness_indicators_data.get("cultural_sensitivity", False),
                language_inclusivity=fairness_indicators_data.get("language_inclusivity", False),
            )
            
            # Get scores (handle backward compatibility with "score" field)
            bias_score = analysis_result.get("bias_score", analysis_result.get("score", 6))
            fairness_score = analysis_result.get("fairness_score", 6)
            overall_score = analysis_result.get("overall_score", (bias_score * 0.6) + (fairness_score * 0.4))
            
            # Use overall_score as the main score for backward compatibility
            main_score = int(round(overall_score))
            
            # Create detailed results
            bias_details = BiasFairnessDetails(
                sub_score_name="Bias & Fairness",
                score=main_score,  # Overall score for backward compatibility
                bias_score=int(bias_score),
                fairness_score=int(fairness_score),
                overall_score=float(overall_score),
                bias_instances=bias_instances,
                fairness_instances=fairness_instances,
                bias_summary=bias_summary,
                fairness_indicators=fairness_indicators,
                explanation=analysis_result.get("explanation", ""),
            )
            
            # Derive boolean flags from analysis
            gender_bias = bias_summary.gender_bias_count > 0
            racial_bias = bias_summary.racial_bias_count > 0
            religious_bias = bias_summary.religious_bias_count > 0
            political_bias = bias_summary.political_bias_count > 0
            cultural_insensitivity = bias_summary.cultural_insensitivity_count > 0
            
        except Exception as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "bias_fairness_analysis_failed",
                error=str(e),
                exc_info=True,
            )
            # Use default values on error
            gender_bias = False
            racial_bias = False
            religious_bias = False
            political_bias = False
            cultural_insensitivity = False
        
        return BiasFairnessSubScore(
            genderBias=gender_bias,
            racialBias=racial_bias,
            religiousBias=religious_bias,
            politicalBias=political_bias,
            culturalInsensitivity=cultural_insensitivity,
            biasFairnessDetails=bias_details,
        )

    async def get_detailed_bias_analysis(
        self,
        response: str,
        judge_platform_id: str = "openai",
        use_llm: bool = True,
    ) -> dict:
        """Get detailed bias analysis with all instances and explanations.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM (must be True)
            
        Returns:
            Dictionary with comprehensive bias analysis
        """
        return await self.bias_analyzer.analyze_bias(
            response, judge_platform_id, use_llm=use_llm
        )

