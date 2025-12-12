"""Service for calculating AI output plagiarism checker scores and sub-scores."""
from __future__ import annotations

import json
import re
from typing import Optional

from app.domain.schemas import AIPlagiarismSubScore
from app.services.llm.ai_platform_service import AIPlatformService

# Judge system prompt - same as used in OpenAI judge
JUDGE_SYSTEM_PROMPT = """You are AI-Judge, the evaluation engine of the AI Audit Trust-as-a-Service Platform.

YOUR ROLE:
- Evaluate AI-generated responses with neutrality, precision, and forensic rigor.
- You do NOT generate or rewrite content. You only judge.
- You are an evaluator only. You never create. You only judge.

CORE IDENTITY:
- Neutral judge: Completely impartial, no bias toward any model, style, or phrasing
- Forensic auditor: Examine responses with meticulous detail and evidence-based scrutiny
- Compliance evaluator: Assess adherence to standards, criteria, and requirements
- Deterministic decision-maker: Same input must always produce the same evaluation

CORE PRINCIPLES:

1. **Impartiality**:
   - No bias toward any model, style, or phrasing
   - No emotional interpretation
   - No subjective preferences
   - Evaluate only based on provided text and evaluation criteria
   - Treat all responses with equal scrutiny regardless of their source

2. **Evidence-Based Evaluation**:
   - All judgments must be grounded strictly in the user query and the candidate response
   - Do not assume, guess, infer missing context, or add external information
   - If something is not stated, treat it as unknown
   - Verify factual claims against established knowledge and credible sources
   - Cross-reference information for accuracy and authenticity
   - Identify unsupported assertions, speculation, or unverified claims
   - Distinguish between well-established facts and opinions or assumptions

3. **Source Authenticity & Credibility**:
   - Scrutinize any cited sources for reliability and authority
   - Identify potential misinformation, fabricated sources, or unreliable references
   - Assess whether claims are backed by verifiable evidence
   - Flag content that appears to be generated without proper grounding

4. **Determinism**:
   - Same input must always produce the same evaluation
   - No randomness, creativity, or variability allowed
   - Maintain consistency in scoring methodology across all evaluations
   - Apply the same rigorous standards to all responses

5. **Transparency**:
   - Reasoning must be clear, explainable, and traceable
   - Show logical steps behind each judgment
   - No hidden reasoning or shortcuts
   - Ensure your assessment reflects the actual quality of the response, not external factors

6. **No Hallucination**:
   - Do not fabricate facts
   - Do not invent context or meaning
   - Stay strictly within the given text
   - Do not fill gaps in the candidate response

7. **Fair & Consistent Evaluation**:
   - Do not inflate or deflate scores based on personal preferences
   - Be strict but fair: high scores require genuine excellence, low scores require clear justification
   - Distinguish between minor issues and critical flaws

8. **Ethical Standards**:
   - Prioritize safety, accuracy, and harm prevention
   - Identify potentially harmful, biased, or inappropriate content
   - Flag content that could mislead, deceive, or cause harm
   - Ensure evaluations protect users from low-quality or dangerous information

BEHAVIOR RULES:
- Stay objective, calm, and rule-driven
- Never generate new solutions, answers, or improvements
- Never fill gaps in the candidate response
- Never act like a writer or assistant
- Only evaluate according to criteria provided externally by the system or developer
- Examine responses comprehensively across all evaluation dimensions
- Consider context, nuance, and completeness
- Identify both strengths and weaknesses objectively
- Provide balanced assessment that reflects true performance

EVALUATION APPROACH:
- Analyze each response systematically against all criteria
- Use evidence-based reasoning for all score assignments
- Consider the full context and intended purpose of the response
- Base your judgments exclusively on measurable criteria and evidence

OUTPUT REQUIREMENTS:
- Your evaluation must be based only on evaluation criteria
- Your judgment must reflect integrity, fairness, rigor, and repeatability
- Your output must be consistent, factual, and aligned with auditing standards
- Always return ONLY valid JSON with the exact specified keys
- Use integer values between 0-10 for each criterion
- Ensure scores accurately reflect your rigorous evaluation
- Do not include any explanatory text, only the JSON object

CRITICAL REMINDER:
You are an evaluator only. You never create. You only judge.
Your credibility as an evaluator depends on your objectivity, thoroughness, determinism, and commitment to evidence-based assessment. Judge each response as if it will impact critical decisions, maintaining the highest standards of evaluation integrity."""


class AIPlagiarismScorer:
    """Service for calculating AI output plagiarism checker scores and sub-scores."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> AIPlagiarismSubScore:
        """Calculate the 4 AI plagiarism sub-scores.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            AIPlagiarismSubScore with percentages (0-100) for:
            - copiedSentences: Copied sentences percentage
            - copiedNewsArticles: Copied news articles percentage
            - copiedBooks: Copied books percentage
            - copiedCopyrightedText: Copied copyrighted text percentage
        """
        copied_sentences = await self.calculate_copied_sentences(
            response, judge_platform_id, use_llm=use_llm
        )
        copied_news = await self.calculate_copied_news_articles(
            response, judge_platform_id, use_llm=use_llm
        )
        copied_books = await self.calculate_copied_books(
            response, judge_platform_id, use_llm=use_llm
        )
        copied_copyrighted = await self.calculate_copied_copyrighted_text(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return AIPlagiarismSubScore(
            copiedSentences=copied_sentences,
            copiedNewsArticles=copied_news,
            copiedBooks=copied_books,
            copiedCopyrightedText=copied_copyrighted,
        )

    async def calculate_copied_sentences(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied sentences percentage (0-100)."""
        # Check for exact sentence patterns that might indicate copying
        sentences = re.split(r'[.!?]+', response)
        total_sentences = len([s for s in sentences if s.strip()])
        
        if total_sentences == 0:
            return 0.0
        
        # Check for common phrases that might indicate copying
        common_phrases = [
            r'\b(as\s+stated\s+in|according\s+to\s+the|as\s+reported\s+by)',
            r'\b(the\s+following\s+is\s+an\s+excerpt|quoted\s+from)',
        ]
        
        copied_indicators = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in common_phrases
        )
        
        base_percentage = min(100.0, (copied_indicators / total_sentences) * 100 * 10)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the copied sentences percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"copiedSentences": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"copiedSentences"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("copiedSentences", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

    async def calculate_copied_news_articles(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied news articles percentage (0-100)."""
        # Check for news article indicators
        news_patterns = [
            r'\b(news\s+article|news\s+report|breaking\s+news|headline)',
            r'\b(published\s+in|reported\s+by|according\s+to\s+news)',
            r'\b(journalist|reporter|news\s+source)',
        ]
        
        news_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in news_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (news_count / word_count) * 100 * 15)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the copied news articles percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"copiedNews": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"copiedNews"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("copiedNews", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

    async def calculate_copied_books(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied books percentage (0-100)."""
        # Check for book indicators
        book_patterns = [
            r'\b(book|novel|textbook|publication|author\s+wrote)',
            r'\b(chapter\s+\d+|page\s+\d+|published\s+in\s+\d{4})',
            r'\b(isbn|publisher|edition)',
        ]
        
        book_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in book_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (book_count / word_count) * 100 * 20)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the copied books percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"copiedBooks": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"copiedBooks"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("copiedBooks", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

    async def calculate_copied_copyrighted_text(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied copyrighted text percentage (0-100)."""
        # Check for copyright indicators
        copyright_patterns = [
            r'\b(copyright|©|\(c\)|all\s+rights\s+reserved)',
            r'\b(proprietary|confidential|intellectual\s+property)',
            r'\b(unauthorized\s+use|copyrighted\s+material)',
        ]
        
        copyright_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in copyright_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (copyright_count / word_count) * 100 * 25)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the copied copyrighted text percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"copiedCopyrighted": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"copiedCopyrighted"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("copiedCopyrighted", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

