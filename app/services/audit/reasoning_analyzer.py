"""Service for analyzing reasoning quality in AI responses."""
from __future__ import annotations

import re
from typing import Any

import structlog

from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class ReasoningAnalyzer:
    """Analyzes step-by-step reasoning, logical consistency, and reasoning quality."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def analyze_reasoning(
        self,
        response: str,
        judge_platform_id: str = "openai",
    ) -> dict[str, Any]:
        """Analyze reasoning quality of the response.
        
        Args:
            response: The AI response to analyze
            judge_platform_id: Platform to use for analysis
            
        Returns:
            Dictionary with reasoning quality score (0-10), findings, and details
        """
        findings = []
        score = 10  # Start with perfect score
        
        # 1. Check for step-by-step reasoning
        step_by_step = await self._check_step_by_step_reasoning(response, judge_platform_id)
        if not step_by_step["present"]:
            findings.append({
                "type": "missing_step_by_step",
                "severity": "medium",
                "description": "Response lacks clear step-by-step reasoning structure"
            })
            score -= 2
        
        # 2. Check for logical consistency
        logical_issues = await self._check_logical_consistency(response, judge_platform_id)
        if logical_issues:
            findings.extend(logical_issues)
            score -= len(logical_issues) * 2  # Deduct 2 points per logical issue
        
        # 3. Check for missing steps
        missing_steps = await self._check_missing_steps(response, judge_platform_id)
        if missing_steps:
            findings.extend(missing_steps)
            score -= len(missing_steps) * 1  # Deduct 1 point per missing step
        
        # 4. Check for wrong logic
        wrong_logic = await self._check_wrong_logic(response, judge_platform_id)
        if wrong_logic:
            findings.extend(wrong_logic)
            score -= len(wrong_logic) * 3  # Deduct 3 points per wrong logic issue
        
        # 5. Check for contradictions in reasoning chain
        contradictions = await self._check_reasoning_contradictions(response, judge_platform_id)
        if contradictions:
            findings.extend(contradictions)
            score -= len(contradictions) * 2  # Deduct 2 points per contradiction
        
        # Ensure score is between 0-10
        score = max(0, min(10, score))
        
        return {
            "score": score,
            "findings": findings,
            "step_by_step_present": step_by_step["present"],
            "logical_consistency": len(logical_issues) == 0,
            "explanation": self._generate_explanation(score, findings)
        }

    async def _check_step_by_step_reasoning(
        self, response: str, judge_platform_id: str
    ) -> dict[str, Any]:
        """Check if response has step-by-step reasoning."""
        # Look for step indicators
        step_indicators = [
            r'\b(step\s+\d+|first|second|third|then|next|finally|lastly)\b',
            r'\b(1\.|2\.|3\.|4\.|5\.)',  # Numbered steps
            r'\b(because|therefore|thus|hence|consequently|as a result)\b',
        ]
        
        has_steps = any(re.search(pattern, response, re.IGNORECASE) for pattern in step_indicators)
        
        # Also check with LLM for more nuanced analysis
        evaluation_prompt = f"""Analyze if the following response demonstrates clear step-by-step reasoning:

Response: {response[:1500]}

Look for:
1. Sequential logical steps
2. Clear progression from premise to conclusion
3. Explicit reasoning connections

Return JSON:
{{
    "present": true/false,
    "reason": "<explanation>"
}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at analyzing reasoning structures in text."
            )
            
            import json
            json_match = re.search(r'\{.*"present".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    return {
                        "present": result.get("present", has_steps),
                        "reason": result.get("reason", "Step-by-step reasoning analysis")
                    }
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("reasoning.step_by_step_check_failed", error=str(e))
        
        return {"present": has_steps, "reason": "Basic pattern matching"}

    async def _check_logical_consistency(
        self, response: str, judge_platform_id: str
    ) -> list[dict[str, Any]]:
        """Check for logical consistency issues."""
        evaluation_prompt = f"""Analyze the following response for logical consistency issues:

Response: {response[:1500]}

Look for:
1. Contradictory statements
2. Circular reasoning
3. Non-sequiturs (conclusions that don't follow from premises)
4. False premises
5. Logical fallacies

Return JSON:
{{
    "issues": [
        {{
            "type": "<issue_type>",
            "description": "<description>",
            "severity": "low|medium|high"
        }}
    ]
}}

If no issues found, return: {{"issues": []}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at detecting logical inconsistencies and fallacies."
            )
            
            import json
            json_match = re.search(r'\{.*"issues".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    issues = result.get("issues", [])
                    findings = []
                    for issue in issues:
                        findings.append({
                            "type": "logical_consistency",
                            "severity": issue.get("severity", "medium"),
                            "description": f"{issue.get('type', 'Logical issue')}: {issue.get('description', '')}"
                        })
                    return findings
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("reasoning.logical_consistency_check_failed", error=str(e))
        
        return []

    async def _check_missing_steps(
        self, response: str, judge_platform_id: str
    ) -> list[dict[str, Any]]:
        """Check for missing steps in reasoning chain."""
        evaluation_prompt = f"""Analyze the following response for missing steps in the reasoning chain:

Response: {response[:1500]}

Look for:
1. Jumps in logic without explanation
2. Assumptions that are not stated
3. Missing intermediate steps between premises and conclusions
4. Gaps in the argument flow

Return JSON:
{{
    "missing_steps": [
        {{
            "description": "<what step is missing>",
            "location": "<where in the reasoning>"
        }}
    ]
}}

If no missing steps found, return: {{"missing_steps": []}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at identifying gaps in reasoning chains."
            )
            
            import json
            json_match = re.search(r'\{.*"missing_steps".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    missing = result.get("missing_steps", [])
                    findings = []
                    for step in missing:
                        findings.append({
                            "type": "missing_step",
                            "severity": "medium",
                            "description": f"Missing step: {step.get('description', 'Unknown')}"
                        })
                    return findings
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("reasoning.missing_steps_check_failed", error=str(e))
        
        return []

    async def _check_wrong_logic(
        self, response: str, judge_platform_id: str
    ) -> list[dict[str, Any]]:
        """Check for wrong logic or incorrect reasoning."""
        evaluation_prompt = f"""Analyze the following response for wrong logic or incorrect reasoning:

Response: {response[:1500]}

Look for:
1. Incorrect logical operations
2. Wrong mathematical or logical conclusions
3. Flawed reasoning patterns
4. Incorrect cause-and-effect relationships

Return JSON:
{{
    "wrong_logic": [
        {{
            "description": "<what is wrong>",
            "correct_approach": "<what should be correct>",
            "severity": "low|medium|high"
        }}
    ]
}}

If no wrong logic found, return: {{"wrong_logic": []}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at identifying incorrect logic and reasoning errors."
            )
            
            import json
            json_match = re.search(r'\{.*"wrong_logic".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    wrong = result.get("wrong_logic", [])
                    findings = []
                    for issue in wrong:
                        findings.append({
                            "type": "wrong_logic",
                            "severity": issue.get("severity", "high"),
                            "description": f"Incorrect logic: {issue.get('description', 'Unknown')}"
                        })
                    return findings
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("reasoning.wrong_logic_check_failed", error=str(e))
        
        return []

    async def _check_reasoning_contradictions(
        self, response: str, judge_platform_id: str
    ) -> list[dict[str, Any]]:
        """Check for contradictions within the reasoning chain."""
        evaluation_prompt = f"""Analyze the following response for contradictions within its reasoning chain:

Response: {response[:1500]}

Look for:
1. Statements that contradict each other
2. Premises that conflict with conclusions
3. Inconsistent reasoning throughout the response

Return JSON:
{{
    "contradictions": [
        {{
            "statement_1": "<first contradictory statement>",
            "statement_2": "<second contradictory statement>",
            "severity": "low|medium|high"
        }}
    ]
}}

If no contradictions found, return: {{"contradictions": []}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at detecting contradictions in reasoning."
            )
            
            import json
            json_match = re.search(r'\{.*"contradictions".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    contradictions = result.get("contradictions", [])
                    findings = []
                    for cont in contradictions:
                        findings.append({
                            "type": "reasoning_contradiction",
                            "severity": cont.get("severity", "medium"),
                            "description": f"Contradiction found: {cont.get('statement_1', '')[:50]} vs {cont.get('statement_2', '')[:50]}"
                        })
                    return findings
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("reasoning.contradictions_check_failed", error=str(e))
        
        return []

    def _generate_explanation(self, score: int, findings: list[dict[str, Any]]) -> str:
        """Generate explanation for the reasoning quality score."""
        if score >= 8:
            base = "High reasoning quality. "
        elif score >= 6:
            base = "Moderate reasoning quality. "
        else:
            base = "Low reasoning quality. "
        
        if not findings:
            return base + "No significant reasoning issues detected."
        
        finding_types = {}
        for finding in findings:
            ftype = finding.get("type", "unknown")
            finding_types[ftype] = finding_types.get(ftype, 0) + 1
        
        details = []
        if "missing_step_by_step" in finding_types:
            details.append("lacks step-by-step structure")
        if "logical_consistency" in finding_types:
            details.append(f"{finding_types['logical_consistency']} logical consistency issue(s)")
        if "missing_step" in finding_types:
            details.append(f"{finding_types['missing_step']} missing step(s)")
        if "wrong_logic" in finding_types:
            details.append(f"{finding_types['wrong_logic']} incorrect logic issue(s)")
        if "reasoning_contradiction" in finding_types:
            details.append(f"{finding_types['reasoning_contradiction']} contradiction(s)")
        
        return base + "Issues found: " + ", ".join(details) + "."

