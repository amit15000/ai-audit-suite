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
        judge_platform_id: str = "openai",
        use_llm: bool = True,
    ) -> ContextAdherenceSubScore:
        """Calculate the 5 context adherence sub-scores.
        
        Uses LLM-based prompt parsing and response analysis to assess adherence.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge (default: "openai")
            use_llm: Whether to use LLM for evaluation (default: True)
        
        Returns:
            ContextAdherenceSubScore with:
            - allInstructions: All instructions adherence percentage (0-100)
            - toneOfVoice: Tone of voice (e.g., 'Polite', 'Professional', 'Casual')
            - lengthConstraints: Length constraints adherence (e.g., 'Short', 'Medium', 'Long')
            - formatRules: Format rules adherence percentage (0-100)
            - brandVoice: Brand voice adherence percentage (0-100)
        """
        # Calculate each sub-score with prompt passed to all scorers
        # Each scorer now returns (score, explanation) tuple
        all_instructions_score, all_instructions_explanation = await self.all_instructions_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        tone_of_voice_result = await self.tone_of_voice_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        length_constraints_result = await self.length_constraints_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        format_rules_score, format_rules_explanation = await self.format_rules_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        brand_voice_score, brand_voice_explanation = await self.brand_voice_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        
        # Handle tone and length which may return string or tuple
        if isinstance(tone_of_voice_result, tuple):
            tone_of_voice, tone_explanation = tone_of_voice_result
        else:
            tone_of_voice = tone_of_voice_result
            tone_explanation = None
        
        if isinstance(length_constraints_result, tuple):
            length_constraints, length_explanation = length_constraints_result
        else:
            length_constraints = length_constraints_result
            length_explanation = None
        
        return ContextAdherenceSubScore(
            allInstructions=all_instructions_score,
            toneOfVoice=tone_of_voice,
            lengthConstraints=length_constraints,
            formatRules=format_rules_score,
            brandVoice=brand_voice_score,
            allInstructionsExplanation=all_instructions_explanation,
            toneOfVoiceExplanation=tone_explanation,
            lengthConstraintsExplanation=length_explanation,
            formatRulesExplanation=format_rules_explanation,
            brandVoiceExplanation=brand_voice_explanation,
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
        score, _ = await self.all_instructions_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        return score

    async def calculate_tone_of_voice(
        self, response: str, prompt: str = "", judge_platform_id: str = "openai", use_llm: bool = True
    ) -> str:
        """Calculate tone of voice (e.g., 'Polite', 'Professional', 'Casual').
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt (optional)
            judge_platform_id: Platform ID for LLM judge (default: "openai")
            use_llm: Whether to use LLM for evaluation (default: True)
            
        Returns:
            Tone of voice string (e.g., 'Polite', 'Professional', 'Casual', 'Formal', 'Neutral')
        """
        tone, _ = await self.tone_of_voice_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        return tone

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
        length, _ = await self.length_constraints_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        return length

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
        score, _ = await self.format_rules_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        return score

    async def calculate_brand_voice(
        self, response: str, prompt: str = "", judge_platform_id: str = "openai", use_llm: bool = True
    ) -> float:
        """Calculate brand voice adherence percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt (optional, may contain brand voice guidelines)
            judge_platform_id: Platform ID for LLM judge (default: "openai")
            use_llm: Whether to use LLM for evaluation (default: True)
            
        Returns:
            Brand voice adherence percentage (0-100)
        """
        score, _ = await self.brand_voice_scorer.calculate_score(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        return score

