"""Service for calculating accuracy scores and sub-scores."""
from __future__ import annotations

import json
import re
from typing import Optional

from app.domain.schemas import AccuracySubScore
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


class AccuracyScorer:
    """Service for calculating accuracy scores and sub-scores."""

    def __init__(self):
        self.ai_service = AIPlatformService()
        self.citation_verifier = CitationVerifier()

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> AccuracySubScore:
        """Calculate the 3 accuracy sub-scores.
        
        Uses rule-based methods first (fast, deterministic), optionally enhanced with LLM.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            AccuracySubScore with scores for:
            - googleBingWikipediaScore: Google/Bing search Wikipedia verification
            - verifiedDatabasesScore: Verified databases (medical, legal, financial, HR)
            - internalCompanyDocsScore: Internal company docs verification
        """
        # Calculate each sub-score (rule-based by default, LLM-enhanced if requested)
        google_bing_wikipedia_score = await self.calculate_google_bing_wikipedia_score(
            response, judge_platform_id, use_llm=use_llm
        )
        verified_databases_score = await self.calculate_verified_databases_score(
            response, judge_platform_id, use_llm=use_llm
        )
        internal_company_docs_score = await self.calculate_internal_company_docs_score(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return AccuracySubScore(
            googleBingWikipediaScore=google_bing_wikipedia_score,
            verifiedDatabasesScore=verified_databases_score,
            internalCompanyDocsScore=internal_company_docs_score,
        )

    async def calculate_google_bing_wikipedia_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for Google/Bing search Wikipedia verification (0-10).
        
        Checks if the response contains information that can be verified against
        Wikipedia and general web search sources.
        Higher score = better accuracy against Wikipedia/web sources.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        """
        # Extract citations and URLs
        verification_results = await self.citation_verifier.verify_all_citations(response)
        citation_stats = self.citation_verifier.get_citation_statistics(verification_results)
        
        # Check for Wikipedia references
        wikipedia_patterns = [
            r'wikipedia\.org',
            r'wikipedia',
            r'en\.wikipedia',
            r'wiki/',
        ]
        wikipedia_count = sum(
            1 for pattern in wikipedia_patterns
            if re.search(pattern, response, re.IGNORECASE)
        )
        
        # Check for general web search indicators
        web_search_indicators = [
            'according to', 'research shows', 'studies indicate',
            'as reported by', 'source:', 'reference:', 'cited in'
        ]
        web_search_count = sum(
            1 for indicator in web_search_indicators
            if indicator in response.lower()
        )
        
        # Base score calculation
        base_score = 6  # Neutral starting point
        
        # Wikipedia references boost score
        if wikipedia_count > 0:
            base_score += min(2, wikipedia_count * 0.5)
        
        # Web search indicators boost score
        if web_search_count > 2:
            base_score += min(2, (web_search_count - 2) * 0.3)
        
        # Citation accessibility boosts score
        if citation_stats['total'] > 0:
            accessibility_rate = citation_stats['accessibility_rate']
            if accessibility_rate >= 0.8:
                base_score += 1
            elif accessibility_rate >= 0.5:
                base_score += 0.5
        
        # Check for factual claims that can be verified
        factual_claims = [
            r'\b\d{4}\b',  # Years
            r'\b\d+%',  # Percentages
            r'\b\d+\.\d+',  # Decimals
        ]
        factual_count = sum(
            len(re.findall(pattern, response)) for pattern in factual_claims
        )
        if factual_count > 3:
            base_score += min(1, factual_count * 0.1)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Evaluate how well this response can be verified against Google/Bing search and Wikipedia sources:

Response: {response[:2000]}

Return ONLY JSON: {{"score": <0-10>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"score"\s*:\s*\d+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    llm_score = int(result.get("score", base_score))
                    # Blend scores (70% rule-based, 30% LLM)
                    base_score = int(base_score * 0.7 + llm_score * 0.3)
            except Exception:
                pass
        
        return max(0, min(10, int(base_score)))

    async def calculate_verified_databases_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for verified databases (medical, legal, financial, HR) (0-10).
        
        Checks if the response references or can be verified against specialized
        databases in medical, legal, financial, or HR domains.
        Higher score = better accuracy against verified databases.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        """
        # Check for domain-specific terminology and references
        medical_keywords = [
            'medical', 'clinical', 'diagnosis', 'treatment', 'patient', 'disease',
            'symptom', 'medication', 'therapy', 'physician', 'hospital', 'health'
        ]
        legal_keywords = [
            'legal', 'law', 'statute', 'regulation', 'court', 'judge', 'attorney',
            'litigation', 'compliance', 'jurisdiction', 'precedent', 'case law'
        ]
        financial_keywords = [
            'financial', 'finance', 'banking', 'investment', 'stock', 'market',
            'revenue', 'profit', 'accounting', 'audit', 'tax', 'securities'
        ]
        hr_keywords = [
            'hr', 'human resources', 'employee', 'workplace', 'hiring', 'recruitment',
            'policy', 'benefits', 'compensation', 'employment', 'workforce'
        ]
        
        medical_count = sum(1 for kw in medical_keywords if kw in response.lower())
        legal_count = sum(1 for kw in legal_keywords if kw in response.lower())
        financial_count = sum(1 for kw in financial_keywords if kw in response.lower())
        hr_count = sum(1 for kw in hr_keywords if kw in response.lower())
        
        # Check for database-like citations
        database_patterns = [
            r'pubmed', r'doi:', r'issn', r'isbn', r'case\s+no\.', r'docket',
            r'sec\s+file', r'fda\s+approval', r'clinical\s+trial'
        ]
        database_count = sum(
            1 for pattern in database_patterns
            if re.search(pattern, response, re.IGNORECASE)
        )
        
        # Base score calculation
        base_score = 4  # Lower default for specialized databases
        
        # Domain-specific content boosts score
        domain_score = 0
        if medical_count > 2:
            domain_score += min(2, medical_count * 0.3)
        if legal_count > 2:
            domain_score += min(2, legal_count * 0.3)
        if financial_count > 2:
            domain_score += min(2, financial_count * 0.3)
        if hr_count > 2:
            domain_score += min(2, hr_count * 0.3)
        
        base_score += domain_score
        
        # Database patterns boost score significantly
        if database_count > 0:
            base_score += min(3, database_count * 1.0)
        
        # Check for formal citations (likely from databases)
        formal_citation_patterns = [
            r'\(\w+\s+et\s+al\.', r'\(\w+,\s+\d{4}\)', r'vol\.\s+\d+', r'pp\.\s+\d+'
        ]
        formal_citations = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in formal_citation_patterns
        )
        if formal_citations > 0:
            base_score += min(2, formal_citations * 0.5)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Evaluate how well this response can be verified against verified databases (medical, legal, financial, HR):

Response: {response[:2000]}

Return ONLY JSON: {{"score": <0-10>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"score"\s*:\s*\d+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    llm_score = int(result.get("score", base_score))
                    # Blend scores (60% rule-based, 40% LLM)
                    base_score = int(base_score * 0.6 + llm_score * 0.4)
            except Exception:
                pass
        
        return max(0, min(10, int(base_score)))

    async def calculate_internal_company_docs_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for internal company docs verification (0-10).
        
        Checks if the response references or can be verified against internal
        company documentation.
        Higher score = better accuracy against internal company docs.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        """
        # Check for internal document indicators
        internal_doc_patterns = [
            r'internal\s+document', r'company\s+policy', r'corporate\s+guideline',
            r'employee\s+handbook', r'standard\s+operating\s+procedure', r'sop',
            r'company\s+standard', r'internal\s+reference', r'corporate\s+document'
        ]
        internal_doc_count = sum(
            1 for pattern in internal_doc_patterns
            if re.search(pattern, response, re.IGNORECASE)
        )
        
        # Check for company-specific terminology
        company_indicators = [
            'internal', 'company', 'corporate', 'organization', 'enterprise',
            'proprietary', 'confidential', 'internal use', 'company-wide'
        ]
        company_count = sum(1 for indicator in company_indicators if indicator in response.lower())
        
        # Check for document references
        doc_reference_patterns = [
            r'doc\s+#?\d+', r'document\s+#?\d+', r'ref\s+#?\d+', r'policy\s+#?\d+',
            r'section\s+\d+', r'chapter\s+\d+', r'version\s+\d+\.\d+'
        ]
        doc_references = sum(
            len(re.findall(pattern, response, re.IGNORECASE))
            for pattern in doc_reference_patterns
        )
        
        # Base score calculation
        base_score = 6  # Neutral starting point
        
        # Internal document patterns boost score
        if internal_doc_count > 0:
            base_score += min(2, internal_doc_count * 0.8)
        
        # Company terminology boosts score
        if company_count > 3:
            base_score += min(1, (company_count - 3) * 0.2)
        
        # Document references boost score
        if doc_references > 0:
            base_score += min(2, doc_references * 0.5)
        
        # Check for structured internal references
        structured_patterns = [
            r'\[internal\]', r'\[company\]', r'\[confidential\]', r'\[proprietary\]'
        ]
        structured_count = sum(
            1 for pattern in structured_patterns
            if re.search(pattern, response, re.IGNORECASE)
        )
        if structured_count > 0:
            base_score += min(1, structured_count * 0.5)
        
        # Optional LLM enhancement
        if use_llm:
            try:
                prompt = f"""Evaluate how well this response can be verified against internal company documentation:

Response: {response[:2000]}

Return ONLY JSON: {{"score": <0-10>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"score"\s*:\s*\d+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    llm_score = int(result.get("score", base_score))
                    # Blend scores (70% rule-based, 30% LLM)
                    base_score = int(base_score * 0.7 + llm_score * 0.3)
            except Exception:
                pass
        
        return max(0, min(10, int(base_score)))

