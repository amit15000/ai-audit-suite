"""Service for calculating safety scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import SafetySubScore
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.safety import (
    ToxicityScorer,
    HateSpeechScorer,
    SexualContentScorer,
    ViolenceScorer,
    DangerousInstructionsScorer,
    SelfHarmSuggestionsScorer,
)


class SafetyScorer:
    """Service for calculating safety scores and sub-scores."""

    def __init__(self):
        """Initialize safety scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.toxicity_scorer = ToxicityScorer(self.ai_service)
        self.hate_speech_scorer = HateSpeechScorer(self.ai_service)
        self.sexual_content_scorer = SexualContentScorer(self.ai_service)
        self.violence_scorer = ViolenceScorer(self.ai_service)
        self.dangerous_instructions_scorer = DangerousInstructionsScorer(self.ai_service)
        self.self_harm_suggestions_scorer = SelfHarmSuggestionsScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> SafetySubScore:
        """Calculate the 6 safety sub-scores.
        
        Uses pattern matching to detect various safety issues.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            SafetySubScore with percentages (0-100) for:
            - toxicity: Toxicity percentage
            - hateSpeech: Hate speech percentage
            - sexualContent: Sexual content percentage
            - violence: Violence percentage
            - dangerousInstructions: Dangerous instructions percentage
            - selfHarmSuggestions: Self-harm suggestions percentage
        """
        # Calculate each sub-score
        toxicity = await self.toxicity_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        hate_speech = await self.hate_speech_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        sexual_content = await self.sexual_content_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        violence = await self.violence_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        dangerous_instructions = await self.dangerous_instructions_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        self_harm = await self.self_harm_suggestions_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return SafetySubScore(
            toxicity=toxicity,
            hateSpeech=hate_speech,
            sexualContent=sexual_content,
            violence=violence,
            dangerousInstructions=dangerous_instructions,
            selfHarmSuggestions=self_harm,
        )

    # Legacy method names for backward compatibility
    async def calculate_toxicity(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate toxicity percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Toxicity percentage (0-100)
        """
        return await self.toxicity_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_hate_speech(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate hate speech percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Hate speech percentage (0-100)
        """
        return await self.hate_speech_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_sexual_content(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate sexual content percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Sexual content percentage (0-100)
        """
        return await self.sexual_content_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_violence(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate violence percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Violence percentage (0-100)
        """
        return await self.violence_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_dangerous_instructions(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate dangerous instructions percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Dangerous instructions percentage (0-100)
        """
        return await self.dangerous_instructions_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_self_harm_suggestions(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate self-harm suggestions percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Self-harm suggestions percentage (0-100)
        """
        return await self.self_harm_suggestions_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

