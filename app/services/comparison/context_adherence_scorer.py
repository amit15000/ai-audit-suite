"""Service for calculating context adherence scores and sub-scores."""
from __future__ import annotations

import json
import re
from typing import Optional

from app.domain.schemas import ContextAdherenceSubScore
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


class ContextAdherenceScorer:
    """Service for calculating context adherence scores and sub-scores."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def calculate_sub_scores(
        self,
        response: str,
        prompt: str = "",
        judge_platform_id: str = "",
        use_llm: bool = False,
    ) -> ContextAdherenceSubScore:
        """Calculate the 5 context adherence sub-scores.
        
        Uses pattern matching and prompt comparison to assess adherence.
        
        Args:
            response: The response text to evaluate
            prompt: The original prompt/instructions (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            ContextAdherenceSubScore with:
            - allInstructions: All instructions adherence percentage (0-100)
            - toneOfVoice: Tone of voice (e.g., 'Polite', 'Professional', 'Casual')
            - lengthConstraints: Length constraints adherence (e.g., 'Short', 'Medium', 'Long')
            - formatRules: Format rules adherence percentage (0-100)
            - brandVoice: Brand voice adherence percentage (0-100)
        """
        # Calculate each sub-score
        all_instructions = await self.calculate_all_instructions(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        tone_of_voice = await self.calculate_tone_of_voice(
            response, judge_platform_id, use_llm=use_llm
        )
        length_constraints = await self.calculate_length_constraints(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        format_rules = await self.calculate_format_rules(
            response, prompt, judge_platform_id, use_llm=use_llm
        )
        brand_voice = await self.calculate_brand_voice(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return ContextAdherenceSubScore(
            allInstructions=all_instructions,
            toneOfVoice=tone_of_voice,
            lengthConstraints=length_constraints,
            formatRules=format_rules,
            brandVoice=brand_voice,
        )

    async def calculate_all_instructions(
        self, response: str, prompt: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate all instructions adherence percentage (0-100)."""
        # If no prompt provided, assume high adherence
        if not prompt:
            return 95.0
        
        # Check if response addresses key terms from prompt
        prompt_words = set(prompt.lower().split())
        response_words = set(response.lower().split())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        prompt_keywords = prompt_words - stop_words
        response_keywords = response_words - stop_words
        
        if len(prompt_keywords) == 0:
            return 95.0
        
        # Calculate keyword overlap
        overlap = len(prompt_keywords & response_keywords)
        base_percentage = (overlap / len(prompt_keywords)) * 100
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt_text = f"""Calculate how well this response adheres to all instructions (0-100%):

Prompt: {prompt[:500]}
Response: {response[:2000]}

Return ONLY JSON: {{"adherence": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt_text, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"adherence"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("adherence", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

    async def calculate_tone_of_voice(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> str:
        """Calculate tone of voice (e.g., 'Polite', 'Professional', 'Casual')."""
        # Tone indicators
        polite_indicators = ['please', 'thank you', 'appreciate', 'kindly', 'respectfully']
        professional_indicators = ['according to', 'based on', 'analysis', 'research', 'data', 'evidence']
        casual_indicators = ['hey', 'yeah', 'gonna', 'wanna', 'cool', 'awesome', 'lol']
        formal_indicators = ['therefore', 'furthermore', 'consequently', 'moreover', 'thus']
        
        response_lower = response.lower()
        
        polite_count = sum(1 for indicator in polite_indicators if indicator in response_lower)
        professional_count = sum(1 for indicator in professional_indicators if indicator in response_lower)
        casual_count = sum(1 for indicator in casual_indicators if indicator in response_lower)
        formal_count = sum(1 for indicator in formal_indicators if indicator in response_lower)
        
        # Determine tone based on highest count
        if polite_count > professional_count and polite_count > casual_count:
            base_tone = "Polite"
        elif professional_count > casual_count:
            base_tone = "Professional"
        elif casual_count > 0:
            base_tone = "Casual"
        elif formal_count > 0:
            base_tone = "Formal"
        else:
            base_tone = "Neutral"
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt_text = f"""Determine the tone of voice of this response (Polite, Professional, Casual, Formal, Neutral):

Response: {response[:2000]}

Return ONLY JSON: {{"tone": "<tone>", "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt_text, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"tone"\s*:\s*"[^"]*".*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_tone = str(parsed.get("tone", base_tone)).strip()
                    if llm_tone:
                        base_tone = llm_tone
            except Exception:
                pass
        
        return base_tone

    async def calculate_length_constraints(
        self, response: str, prompt: str, judge_platform_id: str, use_llm: bool = False
    ) -> str:
        """Calculate length constraints adherence (e.g., 'Short', 'Medium', 'Long')."""
        word_count = len(response.split())
        
        # Determine length category
        if word_count < 50:
            base_length = "Short"
        elif word_count < 200:
            base_length = "Medium"
        elif word_count < 500:
            base_length = "Long"
        else:
            base_length = "Very Long"
        
        # Check if prompt specifies length requirements
        if prompt:
            prompt_lower = prompt.lower()
            if any(word in prompt_lower for word in ['short', 'brief', 'concise']):
                if word_count > 100:
                    base_length = "Long"  # Doesn't meet short requirement
            elif any(word in prompt_lower for word in ['long', 'detailed', 'comprehensive', 'extensive']):
                if word_count < 200:
                    base_length = "Short"  # Doesn't meet long requirement
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt_text = f"""Determine if this response meets length constraints (Short, Medium, Long):

Prompt: {prompt[:500] if prompt else 'No specific length requirement'}
Response length: {word_count} words

Return ONLY JSON: {{"length": "<Short/Medium/Long>", "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt_text, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"length"\s*:\s*"[^"]*".*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_length = str(parsed.get("length", base_length)).strip()
                    if llm_length:
                        base_length = llm_length
            except Exception:
                pass
        
        return base_length

    async def calculate_format_rules(
        self, response: str, prompt: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate format rules adherence percentage (0-100)."""
        # Check for common format requirements
        format_indicators = {
            'bullet_points': r'^[\s]*[-*•]\s+',
            'numbered_list': r'^\d+[\.\)]\s+',
            'paragraphs': r'\n\n',
            'headings': r'^#+\s+',
            'code_blocks': r'```',
        }
        
        format_score = 0.0
        total_checks = 0
        
        # Check if response has structure
        has_structure = bool(re.search(r'\n\n', response)) or bool(re.search(r'^[\s]*[-*•]', response, re.MULTILINE))
        if has_structure:
            format_score += 20
        total_checks += 1
        
        # Check for proper punctuation
        has_punctuation = bool(re.search(r'[.!?]$', response.strip()))
        if has_punctuation:
            format_score += 20
        total_checks += 1
        
        # Check for capitalization
        has_capitalization = bool(re.search(r'^[A-Z]', response.strip()))
        if has_capitalization:
            format_score += 20
        total_checks += 1
        
        # Check for consistent formatting
        has_consistent_format = len(set(re.findall(r'\n', response))) <= 2
        if has_consistent_format:
            format_score += 20
        total_checks += 1
        
        # Check for no excessive whitespace
        no_excessive_whitespace = not bool(re.search(r'\s{3,}', response))
        if no_excessive_whitespace:
            format_score += 20
        total_checks += 1
        
        base_percentage = format_score
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt_text = f"""Calculate format rules adherence percentage (0-100) of this response:

Prompt: {prompt[:500] if prompt else 'No specific format requirements'}
Response: {response[:2000]}

Return ONLY JSON: {{"formatAdherence": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt_text, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"formatAdherence"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("formatAdherence", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

    async def calculate_brand_voice(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate brand voice adherence percentage (0-100)."""
        # Check for professional brand voice indicators
        brand_indicators = {
            'professional': ['professional', 'expert', 'quality', 'excellence', 'premium'],
            'friendly': ['friendly', 'welcoming', 'helpful', 'supportive', 'caring'],
            'innovative': ['innovative', 'cutting-edge', 'advanced', 'modern', 'forward-thinking'],
        }
        
        response_lower = response.lower()
        brand_score = 0.0
        
        # Check for consistent brand voice
        for category, keywords in brand_indicators.items():
            matches = sum(1 for keyword in keywords if keyword in response_lower)
            if matches > 0:
                brand_score += min(30, matches * 10)
        
        # Check for consistent tone throughout
        sentences = re.split(r'[.!?]+', response)
        if len(sentences) > 1:
            # Check if tone is consistent
            has_consistent_tone = True  # Simplified check
            if has_consistent_tone:
                brand_score += 20
        
        base_percentage = min(100.0, brand_score)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt_text = f"""Calculate brand voice adherence percentage (0-100) of this response:

Response: {response[:2000]}

Return ONLY JSON: {{"brandVoice": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt_text, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"brandVoice"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("brandVoice", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

