"""Service for calculating agent action safety audit scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import AgentActionSafetySubScore
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.agent_action_safety import (
    SafeActionScoreScorer,
    RiskWarningsScorer,
    AllowedBlockedDecisionsScorer,
)


class AgentActionSafetyScorer:
    """Service for calculating agent action safety audit scores and sub-scores."""

    def __init__(self):
        """Initialize agent action safety scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.safe_action_score_scorer = SafeActionScoreScorer(self.ai_service)
        self.risk_warnings_scorer = RiskWarningsScorer(self.ai_service)
        self.allowed_blocked_decisions_scorer = AllowedBlockedDecisionsScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> AgentActionSafetySubScore:
        """Calculate the 3 agent action safety sub-scores.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            AgentActionSafetySubScore with:
            - safeActionScore: Safe Action Score percentage (0-100)
            - riskWarnings: Risk warnings percentage (0-100)
            - allowedBlockedDecisions: Allowed/Blocked decisions percentage (0-100)
        """
        safe_action_score = await self.safe_action_score_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        risk_warnings = await self.risk_warnings_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        allowed_blocked = await self.allowed_blocked_decisions_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return AgentActionSafetySubScore(
            safeActionScore=safe_action_score,
            riskWarnings=risk_warnings,
            allowedBlockedDecisions=allowed_blocked,
        )

    # Legacy method names for backward compatibility
    async def calculate_safe_action_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate safe action score percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Safe action score percentage (0-100)
        """
        return await self.safe_action_score_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_risk_warnings(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate risk warnings percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Risk warnings percentage (0-100)
        """
        return await self.risk_warnings_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

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
        return await self.allowed_blocked_decisions_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

