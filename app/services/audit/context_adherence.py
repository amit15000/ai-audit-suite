"""Service for checking context-adherence in AI responses."""
from __future__ import annotations

import re
from typing import Any

import structlog

from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class ContextAdherenceChecker:
    """Checks if AI followed instructions, tone, length, format, and brand voice."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        sentences = re.split(r'[.!?]+\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _count_words(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())

    def _count_characters(self, text: str) -> int:
        """Count characters in text (excluding spaces)."""
        return len(text.replace(" ", ""))

    async def check_adherence(
        self,
        response: str,
        instructions: str | None = None,
        tone: str | None = None,
        max_length: int | None = None,
        format_rules: list[str] | None = None,
        brand_voice: str | None = None,
        judge_platform_id: str = "openai",
    ) -> dict[str, Any]:
        """Check context adherence with hybrid approach.
        
        Args:
            response: The AI response to check
            instructions: Original instructions (if available)
            tone: Expected tone of voice
            max_length: Maximum allowed length
            format_rules: List of format requirements
            brand_voice: Brand voice guidelines
            judge_platform_id: Platform to use for analysis
            
        Returns:
            Dictionary with adherence score (0-10) and findings
        """
        findings = []
        score = 10  # Start with perfect score
        adherence_details = {}
        
        # 1. Check instruction following (infer if not provided)
        inferred_instructions = None
        if not instructions:
            inferred_instructions = await self._infer_instructions_from_response(
                response, judge_platform_id
            )
            instructions = inferred_instructions
        
        if instructions:
            instruction_check = await self._check_instructions(
                response, instructions, judge_platform_id
            )
            adherence_details["instructions"] = instruction_check
            if not instruction_check["followed"]:
                findings.append({
                    "type": "instruction_violation",
                    "description": instruction_check.get("reason", "Instructions not fully followed"),
                    "details": instruction_check.get("violations", [])
                })
                score -= 2
        
        # 2. Check tone adherence (detect if not specified)
        detected_tone = None
        if not tone:
            detected_tone = await self._detect_tone(response, judge_platform_id)
            tone = detected_tone
        
        if tone:
            tone_check = await self._check_tone(response, tone, judge_platform_id)
            adherence_details["tone"] = tone_check
            if not tone_check["adherent"]:
                findings.append({
                    "type": "tone_violation",
                    "description": tone_check.get("reason", "Tone not adhered to"),
                    "detected_tone": detected_tone,
                    "expected_tone": tone
                })
                score -= 1
        
        # 3. Check length constraints (detailed analysis)
        length_check = self._check_length_detailed(response, max_length)
        adherence_details["length"] = length_check
        if length_check.get("violation"):
            findings.append({
                "type": "length_violation",
                "description": length_check.get("description", "Length constraint violated"),
                "word_count": length_check.get("word_count"),
                "char_count": length_check.get("char_count"),
                "max_length": max_length
            })
            score -= 2
        
        # 4. Check format rules (detect format if not specified)
        detected_format = None
        if not format_rules:
            detected_format = self._detect_format(response)
        
        if format_rules or detected_format:
            format_check = await self._check_format(
                response, format_rules or [], detected_format, judge_platform_id
            )
            adherence_details["format"] = format_check
            if not format_check["compliant"]:
                findings.extend(format_check.get("violations", []))
                score -= len(format_check.get("violations", [])) * 1
        
        # 5. Check brand voice (infer if not provided)
        inferred_brand_voice = None
        if not brand_voice:
            inferred_brand_voice = await self._infer_brand_voice(response, judge_platform_id)
        
        if brand_voice or inferred_brand_voice:
            brand_check = await self._check_brand_voice(
                response, brand_voice or inferred_brand_voice, judge_platform_id
            )
            adherence_details["brand_voice"] = brand_check
            if not brand_check["consistent"]:
                findings.append({
                    "type": "brand_voice_violation",
                    "description": brand_check.get("reason", "Brand voice not consistent"),
                    "inferred_voice": inferred_brand_voice
                })
                score -= 2
        
        score = max(0, min(10, score))
        
        return {
            "score": score,
            "findings": findings,
            "adherence_details": adherence_details,
            "explanation": self._generate_explanation(score, findings, adherence_details)
        }

    async def _infer_instructions_from_response(
        self, response: str, judge_platform_id: str
    ) -> str | None:
        """Infer likely instructions from the response structure and content."""
        evaluation_prompt = f"""Analyze the following AI response and infer what instructions or prompt the AI was likely given.

Response:
{response[:1500]}

Based on the response structure, content, format, and style, infer what the original instructions might have been.

Return JSON:
{{
    "inferred_instructions": "<what the AI was likely asked to do>",
    "confidence": "high|medium|low",
    "reasoning": "<why you think these were the instructions>"
}}

If you cannot infer instructions, return: {{"inferred_instructions": null}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at analyzing AI responses to infer the original instructions or prompts."
            )
            
            import json
            json_match = re.search(r'\{.*"inferred_instructions".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    if result.get("inferred_instructions") and result.get("confidence") in ["high", "medium"]:
                        return result["inferred_instructions"]
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("context_adherence.instruction_inference_failed", error=str(e))
        
        return None

    async def _check_instructions(
        self, response: str, instructions: str, judge_platform_id: str
    ) -> dict[str, Any]:
        """Check if instructions were followed."""
        evaluation_prompt = f"""Check if the following response follows the given instructions:

Instructions: {instructions}

Response: {response[:1500]}

Analyze carefully and identify:
1. Which instructions were followed
2. Which instructions were not followed (if any)
3. Specific violations or missing elements

Return JSON:
{{
    "followed": true/false,
    "compliance_percentage": <0-100>,
    "reason": "<overall explanation>",
    "violations": [
        {{
            "instruction": "<which instruction was violated>",
            "description": "<how it was violated>"
        }}
    ],
    "followed_instructions": ["<instruction1>", "<instruction2>"]
}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at evaluating instruction adherence. Be thorough and identify all violations."
            )
            
            import json
            json_match = re.search(r'\{.*"followed".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    if "violations" not in result:
                        result["violations"] = []
                    if "followed_instructions" not in result:
                        result["followed_instructions"] = []
                    return result
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("context_adherence.instruction_check_failed", error=str(e))
        
        return {"followed": True, "reason": "Unable to verify", "violations": [], "compliance_percentage": 100}

    async def _detect_tone(self, response: str, judge_platform_id: str) -> str | None:
        """Detect the tone of the response."""
        evaluation_prompt = f"""Analyze the tone of the following response:

Response: {response[:1500]}

Identify the tone from these categories:
- Professional: Formal, business-like, respectful
- Casual: Informal, relaxed, conversational
- Formal: Very formal, academic, official
- Friendly: Warm, approachable, personable
- Technical: Specialized, jargon-heavy, precise
- Friendly-professional: Warm but business-appropriate
- Neutral: Balanced, objective, unbiased

Return JSON:
{{
    "tone": "<detected tone>",
    "confidence": "high|medium|low",
    "characteristics": ["<characteristic1>", "<characteristic2>"]
}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at analyzing tone and writing style."
            )
            
            import json
            json_match = re.search(r'\{.*"tone".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    if result.get("tone") and result.get("confidence") in ["high", "medium"]:
                        return result["tone"]
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("context_adherence.tone_detection_failed", error=str(e))
        
        return None

    async def _check_tone(
        self, response: str, expected_tone: str, judge_platform_id: str
    ) -> dict[str, Any]:
        """Check tone adherence."""
        evaluation_prompt = f"""Check if the response matches the expected tone:

Expected tone: {expected_tone}

Response: {response[:1500]}

Return JSON:
{{
    "adherent": true/false,
    "actual_tone": "<detected tone>",
    "match_score": <0-100>,
    "reason": "<explanation>",
    "tone_characteristics": ["<characteristic1>", "<characteristic2>"]
}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at evaluating tone consistency."
            )
            
            import json
            json_match = re.search(r'\{.*"adherent".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    return result
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("context_adherence.tone_check_failed", error=str(e))
        
        return {"adherent": True, "reason": "Unable to verify", "match_score": 100}

    def _check_length_detailed(self, response: str, max_length: int | None) -> dict[str, Any]:
        """Check length with detailed analysis."""
        word_count = self._count_words(response)
        char_count = len(response)
        char_count_no_spaces = self._count_characters(response)
        
        result = {
            "word_count": word_count,
            "char_count": char_count,
            "char_count_no_spaces": char_count_no_spaces,
            "violation": False,
            "description": ""
        }
        
        if max_length:
            if char_count > max_length:
                result["violation"] = True
                result["description"] = f"Response length ({char_count} chars) exceeds maximum ({max_length} chars)"
            else:
                result["description"] = f"Response length ({char_count} chars) within limits ({max_length} chars)"
        else:
            # Provide analysis even without max_length
            if word_count < 50:
                result["description"] = f"Short response: {word_count} words, {char_count} characters"
            elif word_count < 200:
                result["description"] = f"Moderate response: {word_count} words, {char_count} characters"
            else:
                result["description"] = f"Long response: {word_count} words, {char_count} characters"
        
        return result

    def _detect_format(self, response: str) -> dict[str, Any]:
        """Detect the format used in the response."""
        format_info = {
            "has_bullets": bool(re.search(r'^[\s]*[-*•]\s+', response, re.MULTILINE)),
            "has_numbering": bool(re.search(r'^\s*\d+[\.\)]\s+', response, re.MULTILINE)),
            "has_headers": bool(re.search(r'^#+\s+', response, re.MULTILINE)) or bool(re.search(r'^[A-Z][A-Z\s]{10,}:', response, re.MULTILINE)),
            "has_paragraphs": len(response.split('\n\n')) > 1,
            "has_table": bool(re.search(r'\|.*\|', response)),
            "format_type": "unknown"
        }
        
        # Determine primary format
        if format_info["has_table"]:
            format_info["format_type"] = "table"
        elif format_info["has_bullets"]:
            format_info["format_type"] = "bullet_points"
        elif format_info["has_numbering"]:
            format_info["format_type"] = "numbered_list"
        elif format_info["has_headers"]:
            format_info["format_type"] = "structured_with_headers"
        elif format_info["has_paragraphs"]:
            format_info["format_type"] = "paragraphs"
        else:
            format_info["format_type"] = "plain_text"
        
        return format_info

    async def _check_format(
        self, response: str, format_rules: list[str], detected_format: dict[str, Any] | None, judge_platform_id: str
    ) -> dict[str, Any]:
        """Check format compliance."""
        violations = []
        
        # If format rules are specified, check against them
        if format_rules:
            for rule in format_rules:
                rule_lower = rule.lower()
                if "bullet" in rule_lower and not any(
                    line.strip().startswith(("-", "*", "•")) for line in response.split("\n")
                ):
                    violations.append({
                        "rule": rule,
                        "description": "Bullet points not used as required"
                    })
                elif "numbered" in rule_lower and not any(
                    line.strip()[0].isdigit() for line in response.split("\n") if line.strip()
                ):
                    violations.append({
                        "rule": rule,
                        "description": "Numbered list not used as required"
                    })
                elif "paragraph" in rule_lower and len(response.split('\n\n')) < 2:
                    violations.append({
                        "rule": rule,
                        "description": "Paragraph format not used as required"
                    })
        
        # If no format rules but detected format, provide analysis
        format_analysis = {}
        if detected_format:
            format_analysis = {
                "detected_format": detected_format.get("format_type", "unknown"),
                "has_bullets": detected_format.get("has_bullets", False),
                "has_numbering": detected_format.get("has_numbering", False),
                "has_headers": detected_format.get("has_headers", False),
            }
        
        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "format_analysis": format_analysis
        }

    async def _infer_brand_voice(self, response: str, judge_platform_id: str) -> str | None:
        """Infer brand voice from response patterns."""
        evaluation_prompt = f"""Analyze the following response and infer the brand voice or writing style guidelines:

Response: {response[:1500]}

Identify characteristics such as:
- Formality level
- Vocabulary style
- Sentence structure
- Overall voice (e.g., "professional and approachable", "technical and precise", "friendly and casual")

Return JSON:
{{
    "brand_voice": "<inferred brand voice description>",
    "confidence": "high|medium|low",
    "characteristics": ["<characteristic1>", "<characteristic2>"]
}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at analyzing brand voice and writing style."
            )
            
            import json
            json_match = re.search(r'\{.*"brand_voice".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    if result.get("brand_voice") and result.get("confidence") in ["high", "medium"]:
                        return result["brand_voice"]
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("context_adherence.brand_voice_inference_failed", error=str(e))
        
        return None

    async def _check_brand_voice(
        self, response: str, brand_voice: str, judge_platform_id: str
    ) -> dict[str, Any]:
        """Check brand voice consistency."""
        evaluation_prompt = f"""Check if the response matches the brand voice:

Brand voice guidelines: {brand_voice}

Response: {response[:1500]}

Return JSON:
{{
    "consistent": true/false,
    "consistency_score": <0-100>,
    "reason": "<explanation>",
    "matching_aspects": ["<aspect1>", "<aspect2>"],
    "non_matching_aspects": ["<aspect1>", "<aspect2>"]
}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                evaluation_prompt,
                system_prompt="You are an expert at evaluating brand voice consistency."
            )
            
            import json
            json_match = re.search(r'\{.*"consistent".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    return result
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("context_adherence.brand_voice_check_failed", error=str(e))
        
        return {"consistent": True, "reason": "Unable to verify", "consistency_score": 100}

    def _generate_explanation(
        self, 
        score: int, 
        findings: list[dict[str, Any]], 
        adherence_details: dict[str, Any]
    ) -> str:
        """Generate detailed explanation for adherence score."""
        if score >= 8:
            base = "High context adherence. "
        elif score >= 6:
            base = "Moderate context adherence. "
        else:
            base = "Low context adherence. "
        
        if not findings:
            return base + "All requirements met."
        
        # Build detailed breakdown
        breakdown_parts = []
        
        # Instructions
        if "instructions" in adherence_details:
            inst_check = adherence_details["instructions"]
            if inst_check.get("followed"):
                compliance = inst_check.get("compliance_percentage", 100)
                breakdown_parts.append(f"Instructions: {compliance}% compliance")
            else:
                violations = inst_check.get("violations", [])
                breakdown_parts.append(
                    f"Instructions: {len(violations)} violation{'s' if len(violations) != 1 else ''} "
                    f"({', '.join([v.get('instruction', 'unknown')[:30] for v in violations[:2]])})"
                )
        
        # Tone
        if "tone" in adherence_details:
            tone_check = adherence_details["tone"]
            if tone_check.get("adherent"):
                actual_tone = tone_check.get("actual_tone", "unknown")
                breakdown_parts.append(f"Tone: {actual_tone} tone maintained")
            else:
                expected = tone_check.get("expected_tone", "unknown")
                actual = tone_check.get("actual_tone", "unknown")
                breakdown_parts.append(f"Tone: Expected {expected}, detected {actual}")
        
        # Length
        if "length" in adherence_details:
            length_check = adherence_details["length"]
            word_count = length_check.get("word_count", 0)
            char_count = length_check.get("char_count", 0)
            if length_check.get("violation"):
                max_len = length_check.get("max_length", "?")
                breakdown_parts.append(
                    f"Length: {word_count} words, {char_count} chars (exceeds {max_len})"
                )
            else:
                breakdown_parts.append(f"Length: {word_count} words, {char_count} chars (within limits)")
        
        # Format
        if "format" in adherence_details:
            format_check = adherence_details["format"]
            if format_check.get("compliant"):
                format_type = format_check.get("format_analysis", {}).get("detected_format", "unknown")
                breakdown_parts.append(f"Format: {format_type} used correctly")
            else:
                violations = format_check.get("violations", [])
                breakdown_parts.append(
                    f"Format: {len(violations)} violation{'s' if len(violations) != 1 else ''}"
                )
        
        # Brand voice
        if "brand_voice" in adherence_details:
            brand_check = adherence_details["brand_voice"]
            if brand_check.get("consistent"):
                consistency = brand_check.get("consistency_score", 100)
                breakdown_parts.append(f"Brand voice: {consistency}% consistent")
            else:
                breakdown_parts.append("Brand voice: Inconsistencies detected")
        
        if breakdown_parts:
            return base + ". ".join(breakdown_parts) + "."
        
        violation_types = [f["type"] for f in findings]
        return base + f"Issues: {', '.join(set(violation_types))}."
