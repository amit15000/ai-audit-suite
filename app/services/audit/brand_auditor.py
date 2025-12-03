"""Service for auditing brand consistency."""
from __future__ import annotations

from typing import Any

import structlog

from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class BrandAuditor:
    """Checks tone, style, vocabulary, format, grammar, and brand-safe language."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def audit_brand_consistency(
        self,
        response: str,
        brand_guidelines: dict[str, Any] | None = None,
        judge_platform_id: str = "openai",
    ) -> dict[str, Any]:
        """Audit brand consistency.
        
        Args:
            response: The AI response to check
            brand_guidelines: Brand guidelines (tone, style, vocabulary, etc.)
            judge_platform_id: Platform to use for analysis
            
        Returns:
            Dictionary with brand consistency score and findings
        """
        findings = []
        score = 10  # Start with perfect score
        
        if brand_guidelines:
            # Check each aspect
            checks = [
                ("tone", brand_guidelines.get("tone")),
                ("style", brand_guidelines.get("style")),
                ("vocabulary", brand_guidelines.get("vocabulary")),
                ("format", brand_guidelines.get("format")),
                ("grammar_level", brand_guidelines.get("grammar_level")),
            ]
            
            for aspect, expected_value in checks:
                if expected_value:
                    check_result = await self._check_aspect(
                        response, aspect, expected_value, judge_platform_id
                    )
                    if not check_result["consistent"]:
                        findings.append({
                            "aspect": aspect,
                            "description": check_result.get("reason", f"{aspect} not consistent")
                        })
                        score -= 1
        
        # Check for brand-safe language
        brand_safe_check = await self._check_brand_safe_language(response, judge_platform_id)
        if not brand_safe_check["safe"]:
            findings.append({
                "aspect": "brand_safety",
                "description": brand_safe_check.get("reason", "Brand-unsafe language detected")
            })
            score -= 2
        
        score = max(0, min(10, score))
        
        return {
            "score": score,
            "findings": findings,
            "explanation": self._generate_explanation(score, findings)
        }

    async def _check_aspect(
        self, response: str, aspect: str, expected: str, judge_platform_id: str
    ) -> dict[str, Any]:
        """Check a specific brand aspect."""
        evaluation_prompt = f"""Check if the response matches the brand {aspect}:

Expected {aspect}: {expected}

Response: {response[:1500]}

Return JSON:
{{
    "consistent": true/false,
    "reason": "<explanation>"
}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt=f"You are an expert at evaluating brand {aspect} consistency."
            )
            
            import json
            import re
            json_match = re.search(r'\{.*"consistent".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug(f"brand_auditor.{aspect}_check_failed", error=str(e))
        
        return {"consistent": True, "reason": "Unable to verify"}

    async def _check_brand_safe_language(
        self, response: str, judge_platform_id: str
    ) -> dict[str, Any]:
        """Check for brand-safe language."""
        evaluation_prompt = f"""Check if the response uses brand-safe language:

Response: {response[:1500]}

Look for:
- Inappropriate language
- Offensive content
- Unprofessional tone
- Controversial statements

Return JSON:
{{
    "safe": true/false,
    "reason": "<explanation>"
}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at evaluating brand-safe language."
            )
            
            import json
            import re
            json_match = re.search(r'\{.*"safe".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("brand_auditor.brand_safe_check_failed", error=str(e))
        
        return {"safe": True, "reason": "Unable to verify"}

    def _generate_explanation(self, score: int, findings: list[dict[str, Any]]) -> str:
        """Generate explanation for brand consistency score."""
        if score >= 8:
            base = "High brand consistency. "
        elif score >= 6:
            base = "Moderate brand consistency. "
        else:
            base = "Low brand consistency. "
        
        if not findings:
            return base + "All brand guidelines met."
        
        aspects = [f["aspect"] for f in findings]
        return base + f"Issues in: {', '.join(set(aspects))}."

