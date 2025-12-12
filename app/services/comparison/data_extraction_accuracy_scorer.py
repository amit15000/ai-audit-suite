"""Service for calculating data extraction accuracy audit scores and sub-scores."""
from __future__ import annotations

import json
import re
from typing import Optional

from app.domain.schemas import DataExtractionAccuracySubScore
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


class DataExtractionAccuracyScorer:
    """Service for calculating data extraction accuracy audit scores and sub-scores."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def calculate_sub_scores(
        self,
        response: str,
        ground_truth: str = "",
        judge_platform_id: str = "",
        use_llm: bool = False,
    ) -> DataExtractionAccuracySubScore:
        """Calculate the 3 data extraction accuracy sub-scores.
        
        Args:
            response: The response text to evaluate
            ground_truth: Ground truth text for comparison (optional)
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            DataExtractionAccuracySubScore with percentages (0-100) for:
            - compareExtractedTextWithGroundTruth: Compare extracted text with ground truth percentage
            - detectExtractionErrors: Detect extraction errors percentage
            - flagMismatchedValues: Flag mismatched values percentage
        """
        compare_ground_truth = await self.calculate_compare_extracted_text_with_ground_truth(
            response, ground_truth, judge_platform_id, use_llm=use_llm
        )
        detect_errors = await self.calculate_detect_extraction_errors(
            response, judge_platform_id, use_llm=use_llm
        )
        flag_mismatched = await self.calculate_flag_mismatched_values(
            response, ground_truth, judge_platform_id, use_llm=use_llm
        )
        
        return DataExtractionAccuracySubScore(
            compareExtractedTextWithGroundTruth=compare_ground_truth,
            detectExtractionErrors=detect_errors,
            flagMismatchedValues=flag_mismatched,
        )

    async def calculate_compare_extracted_text_with_ground_truth(
        self, response: str, ground_truth: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate compare extracted text with ground truth percentage (0-100)."""
        if not ground_truth:
            # No ground truth available, assume high accuracy
            return 100.0
        
        # Simple word-based comparison
        response_words = set(response.lower().split())
        ground_truth_words = set(ground_truth.lower().split())
        
        if not ground_truth_words:
            return 100.0
        
        # Calculate overlap
        intersection = len(response_words & ground_truth_words)
        base_percentage = (intersection / len(ground_truth_words)) * 100
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Compare extracted text with ground truth and calculate accuracy (0-100%):

Ground Truth: {ground_truth[:500]}
Extracted Text: {response[:2000]}

Return ONLY JSON: {{"accuracy": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"accuracy"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("accuracy", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

    async def calculate_detect_extraction_errors(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate detect extraction errors percentage (0-100)."""
        # Error detection patterns
        error_patterns = [
            r'\b(error|mistake|incorrect|wrong|invalid|failed|failure)',
            r'\b(missing\s+data|incomplete\s+extraction|partial\s+data)',
            r'\b(extraction\s+error|parsing\s+error|format\s+error)',
        ]
        
        error_count = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in error_patterns
        )
        
        word_count = len(response.split())
        if word_count == 0:
            return 0.0
        
        base_percentage = min(100.0, (error_count / word_count) * 100 * 30)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the extraction errors detected percentage (0-100) in this response:

Response: {response[:2000]}

Return ONLY JSON: {{"extractionErrors": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"extractionErrors"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("extractionErrors", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

    async def calculate_flag_mismatched_values(
        self, response: str, ground_truth: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate flag mismatched values percentage (0-100)."""
        if not ground_truth:
            return 0.0
        
        # Extract numbers and key values
        response_numbers = set(re.findall(r'\b\d+\.?\d*\b', response))
        ground_truth_numbers = set(re.findall(r'\b\d+\.?\d*\b', ground_truth))
        
        if not ground_truth_numbers:
            return 0.0
        
        # Find mismatches
        mismatches = ground_truth_numbers - response_numbers
        mismatch_percentage = (len(mismatches) / len(ground_truth_numbers)) * 100 if ground_truth_numbers else 0.0
        
        base_percentage = min(100.0, mismatch_percentage * 10)  # Scale up
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Calculate the mismatched values percentage (0-100) between ground truth and extracted text:

Ground Truth: {ground_truth[:500]}
Extracted Text: {response[:2000]}

Return ONLY JSON: {{"mismatchedValues": <0-100>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"mismatchedValues"\s*:\s*[\d.]+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result_json = json_match.group(0)
                    parsed = json.loads(result_json)
                    llm_percentage = float(parsed.get("mismatchedValues", base_percentage))
                    base_percentage = base_percentage * 0.6 + llm_percentage * 0.4
            except Exception:
                pass
        
        return max(0.0, min(100.0, base_percentage))

