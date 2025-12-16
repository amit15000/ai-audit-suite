"""Service for calculating context adherence scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import ContextAdherenceSubScore
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.context_adherence import (
    AllInstructionsScorer,
    ToneOfVoiceScorer,
    LengthConstraintsScorer,
    FormatRulesScorer,
    BrandVoiceScorer,
)


class ContextAdherenceScorer:
    """Service for calculating context adherence scores and sub-scores."""

    def __init__(self):
        """Initialize context adherence scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.all_instructions_scorer = AllInstructionsScorer(self.ai_service)
        self.tone_of_voice_scorer = ToneOfVoiceScorer(self.ai_service)
        self.length_constraints_scorer = LengthConstraintsScorer(self.ai_service)
        self.format_rules_scorer = FormatRulesScorer(self.ai_service)
        self.brand_voice_scorer = BrandVoiceScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        prompt: str = "",
        judge_platform_id: str = "",
        use_llm: bool = False,
    ) -> ContextAdherenceSubScore:
        """Calculate the 5 context adherence sub-scores.
        
        Uses pattern matching and prompt comparison to assess adherence.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            ContextAdherenceSubScore with:
            - allInstructions: All instructions adherence percentage (0-100)
            - toneOfVoice: Tone of voice (e.g., 'Polite', 'Professional', 'Casual')
            - lengthConstraints: Length constraints adherence (e.g., 'Short', 'Medium', 'Long')
            - formatRules: Format rules adherence percentage (0-100)
            - brandVoice: Brand voice adherence percentage (0-100)
        """
        # Calculate each sub-score
        all_instructions = await self.all_instructions_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        tone_of_voice = await self.tone_of_voice_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        length_constraints = await self.length_constraints_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        format_rules = await self.format_rules_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        brand_voice = await self.brand_voice_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return ContextAdherenceSubScore(
            allInstructions=all_instructions,
            toneOfVoice=tone_of_voice,
            lengthConstraints=length_constraints,
            formatRules=format_rules,
            brandVoice=brand_voice,
        )

    # Legacy method names for backward compatibility
    async def calculate_all_instructions(
        self, response: str, prompt: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate all instructions adherence percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            All instructions adherence percentage (0-100)
        """
        return await self.all_instructions_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )

    async def calculate_tone_of_voice(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> str:
        """Calculate tone of voice (e.g., 'Polite', 'Professional', 'Casual').
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Tone of voice string (e.g., 'Polite', 'Professional', 'Casual', 'Formal', 'Neutral')
        """
        return await self.tone_of_voice_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_length_constraints(
        self, response: str, prompt: str, judge_platform_id: str, use_llm: bool = False
    ) -> str:
        """Calculate length constraints adherence (e.g., 'Short', 'Medium', 'Long').
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Length constraints string (e.g., 'Short', 'Medium', 'Long', 'Very Long')
        """
        return await self.length_constraints_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )

    async def calculate_format_rules(
        self, response: str, prompt: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate format rules adherence percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Format rules adherence percentage (0-100)
        """
        return await self.format_rules_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )

    async def calculate_brand_voice(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate brand voice adherence percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Brand voice adherence percentage (0-100)
        """
        return await self.brand_voice_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

