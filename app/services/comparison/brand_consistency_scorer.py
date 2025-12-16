"""Service for calculating brand consistency audit scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import BrandConsistencySubScore
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.brand_consistency import (
    ToneScorer,
    StyleScorer,
    VocabularyScorer,
    FormatScorer,
    GrammarLevelScorer,
    BrandSafeLanguageScorer,
    AllowedBlockedDecisionsScorer,
)


class BrandConsistencyScorer:
    """Service for calculating brand consistency audit scores and sub-scores."""

    def __init__(self):
        """Initialize brand consistency scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.tone_scorer = ToneScorer(self.ai_service)
        self.style_scorer = StyleScorer(self.ai_service)
        self.vocabulary_scorer = VocabularyScorer(self.ai_service)
        self.format_scorer = FormatScorer(self.ai_service)
        self.grammar_level_scorer = GrammarLevelScorer(self.ai_service)
        self.brand_safe_language_scorer = BrandSafeLanguageScorer(self.ai_service)
        self.allowed_blocked_decisions_scorer = AllowedBlockedDecisionsScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> BrandConsistencySubScore:
        """Calculate the 7 brand consistency sub-scores.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            BrandConsistencySubScore with percentages (0-100) for:
            - tone: Tone consistency percentage
            - style: Style consistency percentage
            - vocabulary: Vocabulary consistency percentage
            - format: Format consistency percentage
            - grammarLevel: Grammar level consistency percentage
            - brandSafeLanguage: Brand-safe language percentage
            - allowedBlockedDecisions: Allowed/Blocked decisions percentage
        """
        tone = await self.tone_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)
        style = await self.style_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)
        vocabulary = await self.vocabulary_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)
        format_score = await self.format_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)
        grammar_level = await self.grammar_level_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)
        brand_safe = await self.brand_safe_language_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)
        allowed_blocked = await self.allowed_blocked_decisions_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)
        
        return BrandConsistencySubScore(
            tone=tone,
            style=style,
            vocabulary=vocabulary,
            format=format_score,
            grammarLevel=grammar_level,
            brandSafeLanguage=brand_safe,
            allowedBlockedDecisions=allowed_blocked,
        )

    # Legacy method names for backward compatibility
    async def calculate_tone(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate tone consistency percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Tone consistency percentage (0-100)
        """
        return await self.tone_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)

    async def calculate_style(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate style consistency percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Style consistency percentage (0-100)
        """
        return await self.style_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)

    async def calculate_vocabulary(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate vocabulary consistency percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Vocabulary consistency percentage (0-100)
        """
        return await self.vocabulary_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)

    async def calculate_format(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate format consistency percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Format consistency percentage (0-100)
        """
        return await self.format_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)

    async def calculate_grammar_level(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate grammar level consistency percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Grammar level consistency percentage (0-100)
        """
        return await self.grammar_level_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)

    async def calculate_brand_safe_language(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate brand-safe language percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Brand-safe language percentage (0-100)
        """
        return await self.brand_safe_language_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)

    async def calculate_allowed_blocked_decisions(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate allowed/blocked decisions percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Allowed/blocked decisions percentage (0-100)
        """
        return await self.allowed_blocked_decisions_scorer.calculate_score(response, judge_platform_id, use_llm=use_llm)

