"""Internal company docs score calculation for accuracy detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.accuracy.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_score,
    clamp_score,
)


class InternalCompanyDocsScorer:
    """Calculates internal company docs verification score."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize internal company docs scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
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
            
        Returns:
            Score between 0-10
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
                
                llm_score = extract_json_score(judge_response, int(base_score))
                # Blend scores (70% rule-based, 30% LLM)
                base_score = int(base_score * 0.7 + llm_score * 0.3)
            except Exception:
                pass
        
        return clamp_score(base_score)

