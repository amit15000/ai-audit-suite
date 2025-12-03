"""Service for chatbot evaluation."""
from __future__ import annotations

from typing import Any

import structlog

from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class ChatbotEvaluationService:
    """Evaluates chatbot performance using question variations."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def generate_question_variations(
        self,
        question: str,
        count: int = 5,
        judge_platform_id: str = "openai",
    ) -> list[dict[str, Any]]:
        """Generate N variations of a question."""
        variations = []
        
        for i in range(count):
            variation_prompt = f"""Generate a variation of the following question. The variation should express the same intent but use different wording, style, or phrasing.

Original question: {question}

Generate variation {i+1} that:
- Has the same meaning and intent
- Uses different words or phrasing
- May include typos, abbreviations, or different sentence structure
- Is a natural way someone might ask the same question

Return only the variation question, nothing else."""
            
            try:
                variation = await self.ai_service.get_response(
                    judge_platform_id,
                    variation_prompt,
                    system_prompt="You are an expert at generating natural question variations."
                )
                variations.append({
                    "text": variation.strip(),
                    "type": "paraphrase" if i % 2 == 0 else "rephrase"
                })
            except Exception as e:
                logger.warning("chatbot.variation_generation_failed", iteration=i, error=str(e))
                continue
        
        return variations

    async def generate_correct_answer(
        self,
        question: str,
        judge_platform_id: str = "openai",
    ) -> str:
        """Generate the correct answer for a question."""
        answer_prompt = f"""Provide a comprehensive and accurate answer to the following question:

Question: {question}

Provide a clear, accurate, and complete answer."""
        
        try:
            answer = await self.ai_service.get_response(
                judge_platform_id,
                answer_prompt,
                system_prompt="You are an expert at providing accurate and comprehensive answers."
            )
            return answer.strip()
        except Exception as e:
            logger.warning("chatbot.answer_generation_failed", error=str(e))
            return ""

    async def compare_responses(
        self,
        chatbot_response: str,
        correct_answer: str,
        judge_platform_id: str = "openai",
    ) -> dict[str, Any]:
        """Compare chatbot response with correct answer."""
        comparison_prompt = f"""Compare the chatbot response with the correct answer:

Correct Answer: {correct_answer}

Chatbot Response: {chatbot_response}

Evaluate:
1. Is the chatbot response correct and relevant?
2. Does it address the question properly?
3. What is the similarity score (0-1)?

Return JSON:
{{
    "is_correct": true/false,
    "similarity_score": <0-1>,
    "explanation": "<explanation>"
}}"""
        
        try:
            judge_response = await self.ai_service.get_response(
                judge_platform_id,
                comparison_prompt,
                system_prompt="You are an expert at evaluating chatbot responses."
            )
            
            import json
            import re
            json_match = re.search(r'\{.*"is_correct".*\}', judge_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    return result
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.warning("chatbot.comparison_failed", error=str(e))
        
        # Fallback
        return {
            "is_correct": False,
            "similarity_score": 0.5,
            "explanation": "Comparison evaluation failed"
        }

