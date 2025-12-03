"""Service for detecting hallucinations in AI responses."""
from __future__ import annotations

import re
from typing import Any

import structlog

from app.services.contradiction.contradiction_detector import ContradictionDetector
from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class HallucinationDetector:
    """Detects hallucinations by checking facts, citations, and contradictions."""

    def __init__(self):
        self.ai_service = AIPlatformService()
        self.contradiction_detector = ContradictionDetector()

    async def detect_hallucinations(
        self,
        response: str,
        all_responses: dict[str, str],
        judge_platform_id: str = "openai",
    ) -> dict[str, Any]:
        """Detect hallucinations in the response.
        
        Args:
            response: The AI response to check
            all_responses: All responses from different LLMs for comparison
            judge_platform_id: Platform to use as judge
            
        Returns:
            Dictionary with hallucination score (0-100), findings, and details
        """
        findings = []
        score = 100  # Start with perfect score, deduct for issues
        
        # 1. Check for fabricated citations
        citation_issues = await self._check_citations(response, judge_platform_id)
        if citation_issues:
            findings.extend(citation_issues)
            score -= len(citation_issues) * 15  # Deduct 15 points per fake citation
        
        # 2. Detect contradictions against other LLMs
        if len(all_responses) > 1:
            contradictions = self.contradiction_detector.detect_contradictions(
                all_responses, prompt=None
            )
            if contradictions:
                # Count contradictions involving this response
                response_contradictions = [
                    c for c in contradictions
                    if any(response.lower() in str(c.get("statement_1", "")).lower() or 
                           response.lower() in str(c.get("statement_2", "")).lower()
                           for c in [c])
                ]
                if response_contradictions:
                    findings.append({
                        "type": "contradiction",
                        "severity": "high",
                        "description": f"Found {len(response_contradictions)} contradictions with other LLM responses",
                        "details": response_contradictions[:3]  # Limit details
                    })
                    score -= min(len(response_contradictions) * 10, 40)  # Max 40 points deduction
        
        # 3. Check for contradictory information within the response
        internal_contradictions = await self._check_internal_contradictions(
            response, judge_platform_id
        )
        if internal_contradictions:
            findings.extend(internal_contradictions)
            score -= len(internal_contradictions) * 20  # Deduct 20 points per internal contradiction
        
        # 4. Check for unsupported factual claims
        unsupported_claims = await self._check_unsupported_claims(
            response, judge_platform_id
        )
        if unsupported_claims:
            findings.extend(unsupported_claims)
            score -= len(unsupported_claims) * 10  # Deduct 10 points per unsupported claim
        
        # Ensure score is between 0-100
        score = max(0, min(100, score))
        
        # Convert to 0-10 scale for consistency with other scores
        score_0_10 = int(score / 10)
        
        # Determine color coding (green = low hallucination, red = high)
        if score >= 70:
            color = "green"
        elif score >= 40:
            color = "yellow"
        else:
            color = "red"
        
        # Count unsupported claims
        unsupported_claims_count = len([
            f for f in findings if f.get("type") == "unsupported_claim"
        ])
        
        return {
            "score": score_0_10,  # 0-10 scale
            "score_0_100": score,  # 0-100 scale
            "color": color,
            "findings": findings,
            "unsupported_claims_count": unsupported_claims_count,
            "explanation": self._generate_explanation(score, findings, unsupported_claims_count)
        }

    async def _check_citations(
        self, response: str, judge_platform_id: str
    ) -> list[dict[str, Any]]:
        """Check if citations in the response are fabricated."""
        # Extract URLs and citations from response
        url_pattern = r'https?://[^\s\)]+'
        urls = re.findall(url_pattern, response)
        
        # Extract citation patterns like [1], (Smith, 2023), etc.
        citation_patterns = [
            r'\[(\d+)\]',  # [1], [2]
            r'\([A-Z][a-z]+\s*,\s*\d{4}\)',  # (Smith, 2023)
            r'[A-Z][a-z]+\s+et\s+al\.\s*\(\d{4}\)',  # Smith et al. (2023)
        ]
        
        citations = []
        for pattern in citation_patterns:
            citations.extend(re.findall(pattern, response))
        
        if not urls and not citations:
            return []  # No citations to check
        
        findings = []
        
        # Use judge to evaluate if citations seem fabricated
        evaluation_prompt = f"""Analyze the following AI response and identify any fabricated, fake, or non-existent citations.

Response: {response[:1500]}

Look for:
1. URLs that don't exist or are invalid
2. Citation patterns that don't match real academic formats
3. References to papers/studies that seem made up
4. Suspicious citation patterns

Return a JSON object with:
{{
    "fabricated_citations": [
        {{
            "citation": "<the citation text>",
            "reason": "<why it seems fabricated>",
            "type": "url|citation_pattern|reference"
        }}
    ]
}}

If no fabricated citations are found, return: {{"fabricated_citations": []}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at detecting fabricated citations and references in AI-generated text."
            )
            
            import json
            # Try to extract JSON
            json_match = re.search(r'\{.*"fabricated_citations".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    fabricated = result.get("fabricated_citations", [])
                    for item in fabricated:
                        findings.append({
                            "type": "fabricated_citation",
                            "severity": "high",
                            "description": f"Fabricated citation: {item.get('citation', 'unknown')}",
                            "reason": item.get("reason", "Appears to be fabricated")
                        })
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.warning("hallucination.citation_check_failed", error=str(e))
        
        return findings

    async def _check_internal_contradictions(
        self, response: str, judge_platform_id: str
    ) -> list[dict[str, Any]]:
        """Check for contradictory information within the response itself."""
        evaluation_prompt = f"""Analyze the following AI response for internal contradictions - statements that contradict each other within the same response.

Response: {response[:1500]}

Look for:
1. Numerical contradictions (e.g., "X is 10" and "X is 20")
2. Temporal contradictions (e.g., "happened in 2020" and "happened in 2021")
3. Logical contradictions (e.g., "always true" and "sometimes false")
4. Factual contradictions (e.g., "is a mammal" and "lays eggs")

Return a JSON object with:
{{
    "contradictions": [
        {{
            "statement_1": "<first contradictory statement>",
            "statement_2": "<second contradictory statement>",
            "type": "numerical|temporal|logical|factual",
            "severity": "low|medium|high"
        }}
    ]
}}

If no contradictions are found, return: {{"contradictions": []}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at detecting internal contradictions in text."
            )
            
            import json
            json_match = re.search(r'\{.*"contradictions".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    contradictions = result.get("contradictions", [])
                    findings = []
                    for item in contradictions:
                        findings.append({
                            "type": "internal_contradiction",
                            "severity": item.get("severity", "medium"),
                            "description": f"Internal contradiction: {item.get('type', 'unknown')} type",
                            "details": {
                                "statement_1": item.get("statement_1", ""),
                                "statement_2": item.get("statement_2", "")
                            }
                        })
                    return findings
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.warning("hallucination.internal_contradiction_check_failed", error=str(e))
        
        return []

    async def _check_unsupported_claims(
        self, response: str, judge_platform_id: str
    ) -> list[dict[str, Any]]:
        """Check for unsupported factual claims."""
        evaluation_prompt = f"""Analyze the following AI response and identify unsupported factual claims - statements that appear to be facts but lack evidence, citations, or verification.

Response: {response[:1500]}

Look for:
1. Specific numbers, statistics, or data without sources
2. Historical claims without references
3. Scientific claims without citations
4. Claims about specific events, dates, or people without verification

Return a JSON object with:
{{
    "unsupported_claims": [
        {{
            "claim": "<the unsupported claim>",
            "reason": "<why it appears unsupported>"
        }}
    ]
}}

If no unsupported claims are found, return: {{"unsupported_claims": []}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at identifying unsupported factual claims in text."
            )
            
            import json
            json_match = re.search(r'\{.*"unsupported_claims".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    claims = result.get("unsupported_claims", [])
                    findings = []
                    for item in claims:
                        findings.append({
                            "type": "unsupported_claim",
                            "severity": "medium",
                            "description": f"Unsupported claim: {item.get('claim', 'unknown')[:100]}",
                            "reason": item.get("reason", "Lacks evidence or citation")
                        })
                    return findings
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.warning("hallucination.unsupported_claim_check_failed", error=str(e))
        
        return []

    def _generate_explanation(self, score: int, findings: list[dict[str, Any]], unsupported_claims_count: int = 0) -> str:
        """Generate explanation for the hallucination score."""
        if score >= 70:
            base = "Low hallucination risk. "
        elif score >= 40:
            base = "Moderate hallucination risk. "
        else:
            base = "High hallucination risk. "
        
        if not findings:
            return base + "No significant hallucinations detected."
        
        finding_types = {}
        for finding in findings:
            ftype = finding.get("type", "unknown")
            finding_types[ftype] = finding_types.get(ftype, 0) + 1
        
        details = []
        if "fabricated_citation" in finding_types:
            details.append(f"{finding_types['fabricated_citation']} fabricated citation(s)")
        if "contradiction" in finding_types:
            details.append(f"{finding_types['contradiction']} contradiction(s) with other responses")
        if "internal_contradiction" in finding_types:
            details.append(f"{finding_types['internal_contradiction']} internal contradiction(s)")
        if "unsupported_claim" in finding_types or unsupported_claims_count > 0:
            count = unsupported_claims_count or finding_types.get("unsupported_claim", 0)
            details.append(f"{count} unsupported claim(s)")
        
        return base + "Issues found: " + ", ".join(details) + "."

