"""Service for calculating multi-judge AI review scores and sub-scores."""
from __future__ import annotations

import json
import re
from typing import Dict, Optional

from app.domain.schemas import MultiJudgeAIReviewSubScore
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


class MultiJudgeAIReviewScorer:
    """Service for calculating multi-judge AI review scores and sub-scores."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def calculate_sub_scores(
        self,
        response: str,
        all_responses: Dict[str, str],
        judge_platform_id: str = "",
        use_llm: bool = False,
    ) -> MultiJudgeAIReviewSubScore:
        """Calculate the 3 multi-judge AI review sub-scores.
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            MultiJudgeAIReviewSubScore with percentages (0-100) for:
            - modelVoting: Model voting percentage
            - modelScoring: Model scoring percentage
            - modelCritiques: Model critiques percentage
        """
        model_voting = await self.calculate_model_voting(
            response, all_responses, judge_platform_id, use_llm=use_llm
        )
        model_scoring = await self.calculate_model_scoring(
            response, all_responses, judge_platform_id, use_llm=use_llm
        )
        model_critiques = await self.calculate_model_critiques(
            response, all_responses, judge_platform_id, use_llm=use_llm
        )
        
        return MultiJudgeAIReviewSubScore(
            modelVoting=model_voting,
            modelScoring=model_scoring,
            modelCritiques=model_critiques,
        )

    async def calculate_model_voting(
        self, response: str, all_responses: Dict[str, str], judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate model voting percentage (0-100)."""
        if len(all_responses) <= 1:
            return 100.0  # Only one model, assume 100% voting
        
        # Calculate consensus (voting agreement)
        response_words = set(response.lower().split())
        response_words = {w for w in response_words if len(w) > 2}
        
        agreements = 0
        for other_response in all_responses.values():
            if other_response == response:
                continue
            
            other_words = set(other_response.lower().split())
            other_words = {w for w in other_words if len(w) > 2}
            
            if response_words and other_words:
                intersection = len(response_words & other_words)
                union = len(response_words | other_words)
                similarity = intersection / union if union > 0 else 0
                if similarity > 0.7:  # High similarity = agreement
                    agreements += 1
        
        total_comparisons = len(all_responses) - 1
        if total_comparisons == 0:
            return 100.0
        
        base_percentage = (agreements / total_comparisons) * 100
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the model voting agreement percentage (0-100) across multiple models:

Response: {response[:1000]}
Other responses count: {len(all_responses) - 1}

Return ONLY JSON: {{"modelVoting": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"modelVoting"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("modelVoting", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

    async def calculate_model_scoring(
        self, response: str, all_responses: Dict[str, str], judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate model scoring percentage (0-100)."""
        # Check for scoring indicators
        scoring_patterns = [
            r'\b(score|rating|evaluation|assessment|grade)\s+(of|is|:)\s*\d+',
            r'\b(rated|scored|evaluated|assessed)\s+(at|as|with)\s*\d+',
        ]
        
        scoring_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in scoring_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (scoring_count / word_count) * 100 * 20)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the model scoring percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"modelScoring": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"modelScoring"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("modelScoring", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

    async def calculate_model_critiques(
        self, response: str, all_responses: Dict[str, str], judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate model critiques percentage (0-100)."""
        # Check for critique indicators
        critique_patterns = [
            r'\b(critique|criticism|feedback|review|analysis|evaluation)',
            r'\b(weakness|strength|improvement|suggestion|recommendation)',
            r'\b(positive|negative|good|bad|excellent|poor)\s+(aspect|point|feature)',
        ]
        
        critique_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in critique_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (critique_count / word_count) * 100 * 15)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the model critiques percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"modelCritiques": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"modelCritiques"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("modelCritiques", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

