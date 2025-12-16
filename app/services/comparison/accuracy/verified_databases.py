"""Verified databases score calculation for accuracy detection."""
from __future__ import annotations

import re

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.accuracy.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_score,
    clamp_score,
)


class VerifiedDatabasesScorer:
    """Calculates verified databases (medical, legal, financial, HR) score."""

    def __init__(self, ai_service: AIPlatformService):
        """Initialize verified databases scorer.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service

    async def calculate_score(
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
            
        Returns:
            Score between 0-10
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
                
                llm_score = extract_json_score(judge_response, int(base_score))
                # Blend scores (60% rule-based, 40% LLM)
                base_score = int(base_score * 0.6 + llm_score * 0.4)
            except Exception:
                pass
        
        return clamp_score(base_score)

