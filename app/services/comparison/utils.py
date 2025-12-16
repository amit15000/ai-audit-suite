"""Shared utilities for comparison scoring modules."""

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


def extract_json_score(response: str, default_score: int) -> int:
    """Extract score from LLM JSON response.
    
    Args:
        response: LLM response text
        default_score: Score to use if extraction fails
        
    Returns:
        Extracted score or default_score
    """
    import json
    import re
    
    json_match = re.search(r'\{.*?"score"\s*:\s*\d+.*?\}', response, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group(0))
            return int(result.get("score", default_score))
        except (json.JSONDecodeError, ValueError):
            pass
    return default_score


def extract_json_float(response: str, key: str, default_value: float) -> float:
    """Extract float value from LLM JSON response.
    
    Args:
        response: LLM response text
        key: JSON key to extract
        default_value: Value to use if extraction fails
        
    Returns:
        Extracted float value or default_value
    """
    import json
    import re
    
    json_match = re.search(r'\{.*?"' + re.escape(key) + r'"\s*:\s*[\d.]+.*?\}', response, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group(0))
            return float(result.get(key, default_value))
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    return default_value


def extract_json_bool(response: str, key: str, default_value: bool) -> bool:
    """Extract boolean value from LLM JSON response.
    
    Args:
        response: LLM response text
        key: JSON key to extract
        default_value: Value to use if extraction fails
        
    Returns:
        Extracted boolean value or default_value
    """
    import json
    import re
    
    json_match = re.search(r'\{.*?"' + key + r'"\s*:\s*(true|false).*?\}', response, re.DOTALL | re.IGNORECASE)
    if json_match:
        try:
            result_json = json_match.group(0)
            parsed = json.loads(result_json)
            return bool(parsed.get(key, default_value))
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    return default_value


def clamp_score(score: float, min_score: int = 0, max_score: int = 10) -> int:
    """Clamp score to valid range.
    
    Args:
        score: Score to clamp
        min_score: Minimum score value
        max_score: Maximum score value
        
    Returns:
        Clamped score as integer
    """
    return max(min_score, min(max_score, int(score)))


def clamp_percentage(percentage: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
    """Clamp percentage to valid range.
    
    Args:
        percentage: Percentage to clamp
        min_value: Minimum percentage value
        max_value: Maximum percentage value
        
    Returns:
        Clamped percentage as float
    """
    return max(min_value, min(max_value, float(percentage)))


def extract_json_string(response: str, key: str, default_value: str) -> str:
    """Extract string value from LLM JSON response.
    
    Args:
        response: LLM response text
        key: JSON key to extract
        default_value: Value to use if extraction fails
        
    Returns:
        Extracted string value or default_value
    """
    import json
    import re
    
    json_match = re.search(r'\{.*?"' + key + r'"\s*:\s*"[^"]*".*?\}', response, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group(0))
            extracted = str(result.get(key, default_value)).strip()
            return extracted if extracted else default_value
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    return default_value

