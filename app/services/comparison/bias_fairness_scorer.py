"""Service for calculating bias & fairness scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import BiasFairnessSubScore
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.bias_fairness import (
    GenderBiasScorer,
    RacialBiasScorer,
    ReligiousBiasScorer,
    PoliticalBiasScorer,
    CulturalInsensitivityScorer,
)


class BiasFairnessScorer:
    """Service for calculating bias & fairness scores and sub-scores."""

    def __init__(self):
        """Initialize bias & fairness scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.gender_bias_scorer = GenderBiasScorer(self.ai_service)
        self.racial_bias_scorer = RacialBiasScorer(self.ai_service)
        self.religious_bias_scorer = ReligiousBiasScorer(self.ai_service)
        self.political_bias_scorer = PoliticalBiasScorer(self.ai_service)
        self.cultural_insensitivity_scorer = CulturalInsensitivityScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> BiasFairnessSubScore:
        """Calculate the 5 bias & fairness sub-scores.
        
        Uses pattern matching to detect various types of bias.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            BiasFairnessSubScore with:
            - genderBias: Whether gender bias is detected (Yes/No)
            - racialBias: Whether racial bias is detected (Yes/No)
            - religiousBias: Whether religious bias is detected (Yes/No)
            - politicalBias: Whether political bias is detected (Yes/No)
            - culturalInsensitivity: Whether cultural insensitivity is detected (Yes/No)
        """
        # Calculate each sub-score
        gender_bias = await self.gender_bias_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        racial_bias = await self.racial_bias_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        religious_bias = await self.religious_bias_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        political_bias = await self.political_bias_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        cultural_insensitivity = await self.cultural_insensitivity_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return BiasFairnessSubScore(
            genderBias=gender_bias,
            racialBias=racial_bias,
            religiousBias=religious_bias,
            politicalBias=political_bias,
            culturalInsensitivity=cultural_insensitivity,
        )

    # Legacy method names for backward compatibility
    async def calculate_gender_bias(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if gender bias is detected (Yes/No).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if gender bias is detected, False otherwise
        """
        return await self.gender_bias_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_racial_bias(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if racial bias is detected (Yes/No).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if racial bias is detected, False otherwise
        """
        return await self.racial_bias_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_religious_bias(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if religious bias is detected (Yes/No).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if religious bias is detected, False otherwise
        """
        return await self.religious_bias_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_political_bias(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if political bias is detected (Yes/No).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if political bias is detected, False otherwise
        """
        return await self.political_bias_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_cultural_insensitivity(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if cultural insensitivity is detected (Yes/No).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            True if cultural insensitivity is detected, False otherwise
        """
        return await self.cultural_insensitivity_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

