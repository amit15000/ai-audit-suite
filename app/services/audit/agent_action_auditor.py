"""Service for auditing agent actions before execution."""
from __future__ import annotations

from typing import Any

import structlog

from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class AgentActionAuditor:
    """Audits AI agent actions before execution (email, delete, code change, DB modify)."""

    RISK_ACTIONS = [
        "send_email",
        "delete_record",
        "change_code",
        "modify_database",
        "execute_command",
        "transfer_funds",
        "grant_access",
    ]

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def audit_action(
        self,
        action_type: str,
        action_details: dict[str, Any],
        judge_platform_id: str = "openai",
    ) -> dict[str, Any]:
        """Audit an agent action before execution.
        
        Args:
            action_type: Type of action (e.g., "send_email", "delete_record")
            action_details: Details of the action
            judge_platform_id: Platform to use for risk assessment
            
        Returns:
            Dictionary with safe action score, risk warnings, and allow/block decision
        """
        # Assess risk level
        risk_assessment = await self._assess_risk(action_type, action_details, judge_platform_id)
        
        # Calculate safe action score (0-10, higher is safer)
        risk_level = risk_assessment.get("risk_level", "medium")
        risk_scores = {"low": 9, "medium": 6, "high": 3, "critical": 0}
        safe_action_score = risk_scores.get(risk_level, 5)
        
        # Make allow/block decision
        should_allow = risk_level in ["low", "medium"]
        should_block = risk_level in ["high", "critical"]
        
        return {
            "safe_action_score": safe_action_score,
            "risk_level": risk_level,
            "risk_warnings": risk_assessment.get("warnings", []),
            "allowed": should_allow,
            "blocked": should_block,
            "decision": "allow" if should_allow else "block",
            "reasoning": risk_assessment.get("reasoning", ""),
            "explanation": self._generate_explanation(safe_action_score, risk_level, should_allow)
        }

    async def _assess_risk(
        self, action_type: str, action_details: dict[str, Any], judge_platform_id: str
    ) -> dict[str, Any]:
        """Assess risk of an action."""
        evaluation_prompt = f"""Assess the risk level of the following AI agent action:

Action Type: {action_type}
Action Details: {action_details}

Evaluate the risk and return JSON:
{{
    "risk_level": "low|medium|high|critical",
    "warnings": ["<warning1>", "<warning2>"],
    "reasoning": "<explanation of risk assessment>"
}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at assessing risks of AI agent actions. Be conservative with high-risk actions."
            )
            
            import json
            import re
            json_match = re.search(r'\{.*"risk_level".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("agent_action.risk_assessment_failed", error=str(e))
        
        # Fallback: basic risk assessment
        if action_type in ["delete_record", "modify_database", "execute_command"]:
            return {
                "risk_level": "high",
                "warnings": [f"{action_type} is a high-risk action"],
                "reasoning": "High-risk action type detected"
            }
        elif action_type in ["send_email", "change_code"]:
            return {
                "risk_level": "medium",
                "warnings": [f"{action_type} requires careful review"],
                "reasoning": "Medium-risk action type"
            }
        else:
            return {
                "risk_level": "low",
                "warnings": [],
                "reasoning": "Low-risk action"
            }

    def _generate_explanation(
        self, score: int, risk_level: str, allowed: bool
    ) -> str:
        """Generate explanation for action audit."""
        decision = "ALLOWED" if allowed else "BLOCKED"
        return f"Action {decision}. Risk level: {risk_level.upper()}. Safe action score: {score}/10."

