"""Service for calculating compliance scores and sub-scores."""
from __future__ import annotations

import re
from typing import Optional

from app.domain.schemas import ComplianceSubScore
from app.services.comparison.citation_verifier import CitationVerifier
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


class ComplianceScorer:
    """Service for calculating compliance scores and sub-scores."""

    def __init__(self):
        self.ai_service = AIPlatformService()
        self.citation_verifier = CitationVerifier()

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> ComplianceSubScore:
        """Calculate the 4 compliance sub-scores.
        
        Uses citation verification to check compliance with various standards.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            ComplianceSubScore with:
            - checksUrlsExist: Whether URLs existence is checked (Yes/No)
            - verifiesPapersExist: Whether papers existence is verified (Yes/No)
            - detectsFakeCitations: Whether fake citations are detected (Yes/No)
            - confirmsLegalReferences: Whether legal references are confirmed (Yes/No)
        """
        # Calculate each sub-score
        checks_urls = await self.calculate_checks_urls_exist(
            response, judge_platform_id, use_llm=use_llm
        )
        verifies_papers = await self.calculate_verifies_papers_exist(
            response, judge_platform_id, use_llm=use_llm
        )
        detects_fake = await self.calculate_detects_fake_citations(
            response, judge_platform_id, use_llm=use_llm
        )
        confirms_legal = await self.calculate_confirms_legal_references(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return ComplianceSubScore(
            checksUrlsExist=checks_urls,
            verifiesPapersExist=verifies_papers,
            detectsFakeCitations=detects_fake,
            confirmsLegalReferences=confirms_legal,
        )

    async def calculate_checks_urls_exist(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if URLs existence is checked (Yes/No).
        
        Verifies if URLs in the response are checked for existence and accessibility.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        """
        # Extract and verify URLs
        verification_results = await self.citation_verifier.verify_all_citations(response)
        
        if len(verification_results) == 0:
            # No URLs found, can't check
            return False
        
        # Check if URLs are accessible
        accessible_count = sum(1 for result in verification_results if result.is_accessible)
        total_urls = len(verification_results)
        
        # If most URLs are accessible, checking is successful
        result = (accessible_count / total_urls) >= 0.7 if total_urls > 0 else False
        
        # Optional LLM enhancement
        if use_llm and total_urls > 0:
            try:
                prompt = f"""Check if URLs in this response are verified to exist:

Response: {response[:2000]}

Found {total_urls} URLs, {accessible_count} accessible.

Return ONLY JSON: {{"checks": <true/false>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"checks"\s*:\s*(true|false).*?\}', judge_response, re.DOTALL | re.IGNORECASE)
                if json_match:
                    result_json = json_match.group(0)
                    import json
                    parsed = json.loads(result_json)
                    llm_result = bool(parsed.get("checks", result))
                    result = llm_result
            except Exception:
                pass
        
        return result

    async def calculate_verifies_papers_exist(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if papers existence is verified (Yes/No).
        
        Verifies if academic papers and research documents referenced in the response
        actually exist and are accessible.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        """
        # Extract citations
        verification_results = await self.citation_verifier.verify_all_citations(response)
        
        # Check for paper-like citations
        paper_patterns = [
            r'doi:', r'doi\s*[:\s]+', r'pubmed', r'pmid', r'arxiv', r'issn', r'isbn',
            r'journal', r'proceedings', r'conference', r'paper', r'research\s+paper'
        ]
        
        paper_citations = []
        for result in verification_results:
            citation_text = result.citation.url.lower() + ' ' + (result.citation.text or '').lower()
            if any(re.search(pattern, citation_text, re.IGNORECASE) for pattern in paper_patterns):
                paper_citations.append(result)
        
        if len(paper_citations) == 0:
            # No paper citations found, can't verify
            return False
        
        # Check if papers are accessible
        accessible_papers = sum(1 for result in paper_citations if result.is_accessible)
        accessibility_rate = accessible_papers / len(paper_citations) if paper_citations else 0
        
        # If most papers are accessible, verification is successful
        result = accessibility_rate >= 0.7
        
        # Optional LLM enhancement
        if use_llm and len(paper_citations) > 0:
            try:
                prompt = f"""Check if academic papers in this response are verified to exist:

Response: {response[:2000]}

Found {len(paper_citations)} paper citations, {accessible_papers} accessible.

Return ONLY JSON: {{"verifies": <true/false>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"verifies"\s*:\s*(true|false).*?\}', judge_response, re.DOTALL | re.IGNORECASE)
                if json_match:
                    result_json = json_match.group(0)
                    import json
                    parsed = json.loads(result_json)
                    llm_result = bool(parsed.get("verifies", result))
                    result = llm_result
            except Exception:
                pass
        
        return result

    async def calculate_detects_fake_citations(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if fake citations are detected (Yes/No).
        
        Detects if there are fabricated or fake citations in the response.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        """
        # Extract and verify citations
        verification_results = await self.citation_verifier.verify_all_citations(response)
        citation_stats = self.citation_verifier.get_citation_statistics(verification_results)
        
        if citation_stats['total'] == 0:
            # No citations found, can't detect fake ones
            return False
        
        # Check for suspicious patterns
        suspicious_patterns = [
            'example.com', 'test.com', 'placeholder', 'fake', 'localhost',
            '127.0.0.1', 'dummy', 'sample', 'mock'
        ]
        
        suspicious_count = 0
        for result in verification_results:
            url_lower = result.citation.url.lower()
            if any(pattern in url_lower for pattern in suspicious_patterns):
                suspicious_count += 1
        
        # Check invalid/inaccessible citations
        invalid_rate = citation_stats['invalid'] / citation_stats['total'] if citation_stats['total'] > 0 else 0
        
        # If many citations are invalid or suspicious, fake citations are detected
        result = (invalid_rate > 0.3) or (suspicious_count > 0)
        
        # Optional LLM enhancement
        if use_llm and citation_stats['total'] > 0:
            try:
                invalid_urls = [r.citation.url for r in verification_results if not r.is_accessible][:5]
                suspicious_urls = [
                    r.citation.url for r in verification_results
                    if any(pattern in r.citation.url.lower() for pattern in suspicious_patterns)
                ][:5]
                
                prompt = f"""Check if fake citations are detected in this response:

Response: {response[:2000]}

Invalid/inaccessible URLs: {', '.join(invalid_urls) if invalid_urls else 'None'}
Suspicious URLs: {', '.join(suspicious_urls) if suspicious_urls else 'None'}

Return ONLY JSON: {{"detects": <true/false>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"detects"\s*:\s*(true|false).*?\}', judge_response, re.DOTALL | re.IGNORECASE)
                if json_match:
                    result_json = json_match.group(0)
                    import json
                    parsed = json.loads(result_json)
                    llm_result = bool(parsed.get("detects", result))
                    result = llm_result
            except Exception:
                pass
        
        return result

    async def calculate_confirms_legal_references(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> bool:
        """Check if legal references are confirmed (Yes/No).
        
        Verifies if legal references (cases, statutes, regulations) in the response
        are valid and can be confirmed.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        """
        # Check for legal reference patterns
        legal_patterns = [
            r'case\s+no\.', r'docket', r'statute', r'regulation', r'law\s+no\.',
            r'sec\.', r'section\s+\d+', r'chapter\s+\d+', r'usc\s+\d+', r'cfr\s+\d+',
            r'court\s+case', r'legal\s+precedent', r'judicial', r'jurisdiction'
        ]
        
        legal_references = []
        for pattern in legal_patterns:
            matches = re.finditer(pattern, response, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 50)
                end = min(len(response), match.end() + 50)
                context = response[start:end]
                legal_references.append(context)
        
        if len(legal_references) == 0:
            # No legal references found, can't confirm
            return False
        
        # Check if legal references are in accessible citations
        verification_results = await self.citation_verifier.verify_all_citations(response)
        
        # Check for legal domain indicators in accessible citations
        legal_domain_indicators = [
            'court', 'legal', 'law', 'statute', 'regulation', 'case', 'docket',
            'jurisdiction', 'precedent', 'judicial'
        ]
        
        legal_citations = []
        for result in verification_results:
            if result.is_accessible:
                citation_text = (result.citation.url + ' ' + (result.citation.text or '')).lower()
                if any(indicator in citation_text for indicator in legal_domain_indicators):
                    legal_citations.append(result)
        
        # If we have legal references and accessible legal citations, confirmation is successful
        result = len(legal_citations) > 0 and len(legal_references) > 0
        
        # Optional LLM enhancement
        if use_llm and len(legal_references) > 0:
            try:
                prompt = f"""Check if legal references in this response are confirmed:

Response: {response[:2000]}

Found {len(legal_references)} legal references, {len(legal_citations)} accessible legal citations.

Return ONLY JSON: {{"confirms": <true/false>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"confirms"\s*:\s*(true|false).*?\}', judge_response, re.DOTALL | re.IGNORECASE)
                if json_match:
                    result_json = json_match.group(0)
                    import json
                    parsed = json.loads(result_json)
                    llm_result = bool(parsed.get("confirms", result))
                    result = llm_result
            except Exception:
                pass
        
        return result

