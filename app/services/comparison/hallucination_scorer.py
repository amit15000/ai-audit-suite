"""Service for calculating hallucination scores and sub-scores."""
from __future__ import annotations

import json
import re
from typing import Optional

from app.domain.schemas import HallucinationSubScore
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


class HallucinationScorer:
    """Service for calculating hallucination scores and sub-scores."""

    def __init__(self):
        self.ai_service = AIPlatformService()
        self.citation_verifier = CitationVerifier()

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        all_responses: dict[str, str],
        use_llm: bool = False,
        use_embeddings: bool = False,
    ) -> HallucinationSubScore:
        """Calculate the 4 hallucination sub-scores.
        
        Uses rule-based methods first (fast, deterministic), optionally enhanced with LLM/embeddings.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            all_responses: Dictionary of all LLM responses for comparison
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            use_embeddings: Whether to use embeddings for semantic similarity (default: False)
        
        Returns:
            HallucinationSubScore with scores for:
            - factCheckingScore: Checking facts against external sources
            - fabricatedCitationsScore: Detecting fabricated citations
            - contradictoryInfoScore: Identifying contradictory information
            - multiLLMComparisonScore: Comparing against multiple LLMs
        """
        # Calculate each sub-score (rule-based by default, LLM-enhanced if requested)
        fact_checking_score = await self.calculate_fact_checking_score(
            response, judge_platform_id, use_llm=use_llm
        )
        fabricated_citations_score = await self.calculate_fabricated_citations_score(
            response, judge_platform_id, use_llm=use_llm
        )
        contradictory_info_score = await self.calculate_contradictory_info_score(
            response, judge_platform_id, use_llm=use_llm
        )
        multi_llm_comparison_score = await self.calculate_multi_llm_comparison_score(
            response, all_responses, use_embeddings=use_embeddings
        )
        
        return HallucinationSubScore(
            factCheckingScore=fact_checking_score,
            fabricatedCitationsScore=fabricated_citations_score,
            contradictoryInfoScore=contradictory_info_score,
            multiLLMComparisonScore=multi_llm_comparison_score,
        )

    async def calculate_fact_checking_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for fact-checking against external sources (0-10).
        
        Uses citation verification to check if sources are valid and accessible.
        Higher score = better fact-checking (fewer hallucinations detected).
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        """
        # Extract and verify citations
        verification_results = await self.citation_verifier.verify_all_citations(response)
        citation_stats = self.citation_verifier.get_citation_statistics(verification_results)
        
        # Base score calculation based on citation verification
        if citation_stats['total'] == 0:
            # No citations found - neutral score
            base_score = 6
        else:
            # Score based on citation accessibility
            accessibility_rate = citation_stats['accessibility_rate']
            
            if accessibility_rate >= 0.9:
                base_score = 9  # Almost all citations accessible
            elif accessibility_rate >= 0.7:
                base_score = 8  # Most citations accessible
            elif accessibility_rate >= 0.5:
                base_score = 6  # Half accessible
            elif accessibility_rate >= 0.3:
                base_score = 4  # Few accessible
            else:
                base_score = 2  # Most citations invalid/inaccessible
        
        # Check for factual claim patterns (positive indicators)
        factual_indicators = [
            "according to", "research shows", "studies indicate", "data suggests",
            "evidence indicates", "findings show", "statistics show", "reports indicate",
            "as stated in", "as reported by", "cited in", "referenced in"
        ]
        factual_count = sum(1 for indicator in factual_indicators if indicator in response.lower())
        
        # Check for specific factual claims (numbers, dates, statistics)
        number_pattern = r'\b\d+%|\b\d+\.\d+%|\b\d{4}\b'  # percentages or years
        numbers_found = len(re.findall(number_pattern, response))
        
        # Adjustments based on citation quality
        if citation_stats['total'] > 0:
            # Bonus for having verifiable citations
            if citation_stats['accessible'] > 0:
                base_score += min(1, citation_stats['accessible'] * 0.2)
            # Penalty for invalid citations
            if citation_stats['invalid'] > 0:
                base_score -= min(2, citation_stats['invalid'] * 0.5)
        
        # Check for vague vs specific claims
        vague_indicators = ["many", "some", "often", "usually", "generally", "typically"]
        vague_count = sum(1 for indicator in vague_indicators if indicator in response.lower())
        if vague_count > 3 and citation_stats['total'] == 0:
            base_score -= 1  # Penalty for vague claims without citations
        
        # Check for unverifiable claims (negative indicators)
        unverifiable_patterns = [
            "experts say", "many believe", "it is said", "rumors suggest",
            "some claim", "allegedly", "supposedly"
        ]
        unverifiable_count = sum(1 for pattern in unverifiable_patterns if pattern in response.lower())
        if unverifiable_count > 0 and citation_stats['total'] == 0:
            base_score -= min(2, unverifiable_count * 0.5)
        
        # Optional LLM enhancement for complex cases
        if use_llm and (factual_count > 3 or citation_stats['total'] > 0):
            try:
                # Include citation verification results in prompt
                citation_summary = f"Found {citation_stats['total']} citations, {citation_stats['accessible']} accessible, {citation_stats['invalid']} invalid"
                
                prompt = f"""Evaluate factual accuracy of this response. Citations found: {citation_summary}

Response: {response[:2000]}

Return ONLY JSON: {{"score": <0-10>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"score"\s*:\s*\d+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    llm_score = int(result.get("score", base_score))
                    # Blend manual and LLM scores (60% citation-based, 40% LLM)
                    base_score = int(base_score * 0.6 + llm_score * 0.4)
            except Exception:
                pass  # Fall back to citation-based score
        
        return max(0, min(10, int(base_score)))

    async def calculate_fabricated_citations_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for detecting fabricated citations (0-10).
        
        Uses actual citation verification to check if URLs are valid and accessible.
        Higher score = fewer fabricated citations detected.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced verification (default: False)
        """
        # Extract and verify all citations
        verification_results = await self.citation_verifier.verify_all_citations(response)
        citation_stats = self.citation_verifier.get_citation_statistics(verification_results)
        
        if citation_stats['total'] == 0:
            # No citations found - can't detect fabrication
            return 6
        
        # Score based on citation verification results
        # Higher accessibility rate = fewer fabricated citations
        accessibility_rate = citation_stats['accessibility_rate']
        invalid_rate = citation_stats['invalid'] / citation_stats['total'] if citation_stats['total'] > 0 else 0
        
        # Base score from verification
        if invalid_rate > 0.5:
            base_score = 2  # More than half are invalid (likely fabricated)
        elif invalid_rate > 0.3:
            base_score = 4  # Many invalid
        elif invalid_rate > 0.1:
            base_score = 6  # Some invalid
        elif accessibility_rate >= 0.9:
            base_score = 9  # Almost all accessible (likely real)
        elif accessibility_rate >= 0.7:
            base_score = 8  # Most accessible
        else:
            base_score = 5  # Mixed results
        
        # Check for suspicious URL patterns
        suspicious_patterns = ['example.com', 'test.com', 'placeholder', 'fake', 'localhost', '127.0.0.1']
        suspicious_count = 0
        for result in verification_results:
            url_lower = result.citation.url.lower()
            if any(pattern in url_lower for pattern in suspicious_patterns):
                suspicious_count += 1
        
        if suspicious_count > 0:
            base_score -= min(3, suspicious_count * 1.0)  # Penalty for suspicious URLs
        
        # Check for citation-text mismatch (citations mentioned but not linked)
        citation_mentions = ['cited', 'reference', 'source', 'according to', 'as per', 'as stated in']
        mentions = sum(1 for mention in citation_mentions if mention in response.lower())
        if mentions > citation_stats['total'] * 2:
            base_score -= 1  # More mentions than actual citations
        
        # Check for proper citation formats (bonus)
        academic_pattern = r'\([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*,\s*\d{4}\)'
        academic_citations = len(re.findall(academic_pattern, response))
        if academic_citations > 0:
            base_score += min(1, academic_citations * 0.2)  # Bonus for proper format
        
        # Optional LLM enhancement for complex cases
        if use_llm and (suspicious_count > 0 or citation_stats['total'] > 5):
            try:
                # Include verification results in prompt
                invalid_urls = [r.citation.url for r in verification_results if not r.is_accessible][:5]
                valid_urls = [r.citation.url for r in verification_results if r.is_accessible][:5]
                
                prompt = f"""Verify if these citations are valid or fabricated:

Valid/accessible URLs: {', '.join(valid_urls) if valid_urls else 'None'}
Invalid/inaccessible URLs: {', '.join(invalid_urls) if invalid_urls else 'None'}

Return ONLY JSON: {{"score": <0-10>, "explanation": "<brief>"}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"score"\s*:\s*\d+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    llm_score = int(result.get("score", base_score))
                    # Blend scores (70% verification-based, 30% LLM)
                    base_score = int(base_score * 0.7 + llm_score * 0.3)
            except Exception:
                pass
        
        return max(0, min(10, int(base_score)))

    async def calculate_contradictory_info_score(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> int:
        """Calculate score for identifying contradictory information (0-10).
        
        Uses semantic analysis and claim comparison to detect actual contradictions.
        Higher score = fewer contradictions detected.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced analysis (default: False)
        """
        # Split into sentences for analysis
        sentences = re.split(r'[.!?]+', response)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        if len(sentences) < 2:
            return 9  # Single sentence or too short, no contradictions possible
        
        contradiction_score = 0.0  # Start with 0 contradictions detected
        
        # Method 1: Extract and compare factual claims
        factual_claims = self._extract_factual_claims(sentences)
        contradiction_score += self._detect_claim_contradictions(factual_claims)
        
        # Method 2: Detect semantic contradictions using embeddings (if available)
        try:
            from app.services.embedding.embedding_service import EmbeddingService
            from app.services.embedding.similarity_service import SimilarityService
            
            embedding_service = EmbeddingService()
            similarity_service = SimilarityService()
            
            # Generate embeddings for all sentences
            sentence_embeddings = []
            for sentence in sentences[:20]:  # Limit to first 20 sentences for performance
                try:
                    embedding = await embedding_service.generate_embedding(sentence)
                    sentence_embeddings.append((sentence, embedding))
                except Exception:
                    continue
            
            # Compare sentence pairs for semantic contradictions
            if len(sentence_embeddings) >= 2:
                semantic_contradictions = self._detect_semantic_contradictions(
                    sentence_embeddings, similarity_service
                )
                contradiction_score += semantic_contradictions
        except Exception:
            # If embeddings fail, fall back to text-based analysis
            pass
        
        # Method 3: Detect explicit contradiction patterns (more reliable)
        explicit_contradictions = self._detect_explicit_contradictions(sentences)
        contradiction_score += explicit_contradictions
        
        # Convert contradiction score to final score (0-10)
        # Higher contradiction_score = lower final score
        # Normalize: 0 contradictions = 10, many contradictions = 0
        if contradiction_score == 0:
            final_score = 10
        elif contradiction_score < 1:
            final_score = 9
        elif contradiction_score < 2:
            final_score = 7
        elif contradiction_score < 3:
            final_score = 5
        elif contradiction_score < 4:
            final_score = 3
        else:
            final_score = 1
        
        # Optional LLM enhancement for validation
        if use_llm and contradiction_score > 0:
            try:
                prompt = f"""Analyze this text for internal contradictions. Look for:
1. Conflicting factual claims about the same subject
2. Statements that directly contradict each other
3. Logical inconsistencies

Text: {response[:2000]}

Return ONLY JSON: {{
    "contradictions_found": <number of contradictions>,
    "score": <0-10 where 10=no contradictions, 0=many contradictions>,
    "explanation": "<brief>"
}}"""
                
                judge_response = await self.ai_service.get_response(
                    judge_platform_id, prompt, system_prompt=JUDGE_SYSTEM_PROMPT
                )
                
                json_match = re.search(r'\{.*?"score"\s*:\s*\d+.*?\}', judge_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    llm_score = int(result.get("score", final_score))
                    # Blend scores (60% rule-based, 40% LLM for validation)
                    final_score = int(final_score * 0.6 + llm_score * 0.4)
            except Exception:
                pass
        
        return max(0, min(10, final_score))
    
    def _extract_factual_claims(self, sentences: list[str]) -> list[dict]:
        """Extract factual claims from sentences.
        
        Returns list of claims with subject, value, and sentence index.
        """
        claims = []
        
        # Pattern to extract claims: "X is Y", "X are Y", "X was Y", etc.
        claim_patterns = [
            r'(\w+(?:\s+\w+)*?)\s+(?:is|are|was|were)\s+(\d+[%]?|[\w\s]+?)(?:\.|,|$)',
            r'(\w+(?:\s+\w+)*?)\s+(?:has|have|had)\s+(\d+[%]?|[\w\s]+?)(?:\.|,|$)',
            r'(\w+(?:\s+\w+)*?)\s+(?:equals?|=\s*)(\d+[%]?|[\w\s]+?)(?:\.|,|$)',
        ]
        
        for idx, sentence in enumerate(sentences):
            for pattern in claim_patterns:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    subject = match.group(1).strip().lower()
                    value = match.group(2).strip().lower()
                    if len(subject) > 2 and len(value) > 1:
                        claims.append({
                            'subject': subject,
                            'value': value,
                            'sentence_idx': idx,
                            'sentence': sentence
                        })
        
        return claims
    
    def _detect_claim_contradictions(self, claims: list[dict]) -> float:
        """Detect contradictions in factual claims.
        
        Returns a score indicating number of contradictions found.
        """
        if len(claims) < 2:
            return 0.0
        
        contradiction_count = 0.0
        
        # Group claims by subject
        subject_groups = {}
        for claim in claims:
            subject = claim['subject']
            if subject not in subject_groups:
                subject_groups[subject] = []
            subject_groups[subject].append(claim)
        
        # Check for conflicting values for the same subject
        for subject, subject_claims in subject_groups.items():
            if len(subject_claims) < 2:
                continue
            
            # Extract unique values
            values = [c['value'] for c in subject_claims]
            unique_values = set(values)
            
            # If same subject has different values, potential contradiction
            if len(unique_values) > 1:
                # Check if values are actually contradictory (not just different)
                # Numbers that are very different are more likely contradictions
                numeric_values = []
                for val in unique_values:
                    # Extract numbers
                    nums = re.findall(r'\d+\.?\d*', val)
                    if nums:
                        numeric_values.extend([float(n) for n in nums])
                
                if numeric_values:
                    # If numbers differ significantly, it's a contradiction
                    if max(numeric_values) / min(numeric_values) > 2.0:
                        contradiction_count += 1.0
                else:
                    # Non-numeric: check if values are semantically opposite
                    # Simple check: if one contains negation of the other
                    value_list = list(unique_values)
                    for i, val1 in enumerate(value_list):
                        for val2 in value_list[i+1:]:
                            if self._are_opposite_values(val1, val2):
                                contradiction_count += 0.5
        
        return contradiction_count
    
    def _are_opposite_values(self, val1: str, val2: str) -> bool:
        """Check if two values are semantically opposite."""
        # Simple heuristic: check for negation patterns
        opposites = [
            ('true', 'false'), ('yes', 'no'), ('correct', 'incorrect'),
            ('right', 'wrong'), ('exists', 'not exist'), ('present', 'absent'),
            ('positive', 'negative'), ('increase', 'decrease'), ('up', 'down'),
            ('more', 'less'), ('greater', 'smaller'), ('high', 'low')
        ]
        
        val1_lower = val1.lower()
        val2_lower = val2.lower()
        
        for opp1, opp2 in opposites:
            if (opp1 in val1_lower and opp2 in val2_lower) or \
               (opp2 in val1_lower and opp1 in val2_lower):
                return True
        
        # Check for explicit negation
        if ('not' in val1_lower and val2_lower.replace('not ', '').replace('not', '') in val1_lower) or \
           ('not' in val2_lower and val1_lower.replace('not ', '').replace('not', '') in val2_lower):
            return True
        
        return False
    
    def _detect_semantic_contradictions(
        self, 
        sentence_embeddings: list[tuple[str, list[float]]],
        similarity_service
    ) -> float:
        """Detect semantic contradictions using embeddings.
        
        Compares sentence embeddings to find semantically opposite statements.
        """
        if len(sentence_embeddings) < 2:
            return 0.0
        
        contradiction_count = 0.0
        
        # Compare each sentence pair
        for i, (sent1, emb1) in enumerate(sentence_embeddings):
            for j, (sent2, emb2) in enumerate(sentence_embeddings[i+1:], start=i+1):
                # Calculate similarity
                similarity = similarity_service.cosine_similarity(emb1, emb2)
                
                # Low similarity might indicate contradiction, but we need to check
                # if they're about the same topic (opposite) vs different topics
                if similarity < 0.3:  # Very different
                    # Check if they mention similar subjects (potential contradiction)
                    sent1_words = set(sent1.lower().split())
                    sent2_words = set(sent2.lower().split())
                    common_words = sent1_words & sent2_words
                    
                    # If they share significant words but are semantically different,
                    # might be a contradiction
                    if len(common_words) >= 3 and len(common_words) / max(len(sent1_words), len(sent2_words)) > 0.2:
                        # Check for negation patterns
                        if self._has_negation_relationship(sent1, sent2):
                            contradiction_count += 0.5
        
        return contradiction_count
    
    def _has_negation_relationship(self, sent1: str, sent2: str) -> bool:
        """Check if two sentences have a negation relationship."""
        # Check for explicit contradiction words
        contradiction_markers = [
            'but', 'however', 'although', 'despite', 'whereas',
            'on the other hand', 'conversely', 'in contrast'
        ]
        
        sent1_lower = sent1.lower()
        sent2_lower = sent2.lower()
        
        # If one sentence contains a contradiction marker, check if they're related
        for marker in contradiction_markers:
            if marker in sent1_lower or marker in sent2_lower:
                # Check if they share subjects
                sent1_words = set(sent1_lower.split())
                sent2_words = set(sent2_lower.split())
                if len(sent1_words & sent2_words) >= 2:
                    return True
        
        return False
    
    def _detect_explicit_contradictions(self, sentences: list[str]) -> float:
        """Detect explicit contradictions using pattern matching.
        
        Looks for clear contradiction patterns like "X is Y, but X is not Y".
        """
        contradiction_count = 0.0
        
        # Pattern: "X is Y" followed by "X is not Y" or "X is Z" (where Z contradicts Y)
        for i, sent1 in enumerate(sentences):
            for sent2 in sentences[i+1:]:
                # Extract subjects and predicates
                sent1_claims = re.findall(r'(\w+(?:\s+\w+)*?)\s+(?:is|are|was|were)\s+([^.]+)', sent1, re.IGNORECASE)
                sent2_claims = re.findall(r'(\w+(?:\s+\w+)*?)\s+(?:is|are|was|were)\s+([^.]+)', sent2, re.IGNORECASE)
                
                for subj1, pred1 in sent1_claims:
                    for subj2, pred2 in sent2_claims:
                        # Check if same subject
                        if subj1.lower().strip() == subj2.lower().strip():
                            pred1_lower = pred1.lower().strip()
                            pred2_lower = pred2.lower().strip()
                            
                            # Check for explicit negation
                            if ('not' in pred2_lower and pred2_lower.replace('not ', '').replace('not', '').strip() in pred1_lower) or \
                               ('not' in pred1_lower and pred1_lower.replace('not ', '').replace('not', '').strip() in pred2_lower):
                                contradiction_count += 1.0
                            # Check if predicates are opposite
                            elif self._are_opposite_values(pred1_lower, pred2_lower):
                                contradiction_count += 0.5
        
        return contradiction_count

    async def calculate_multi_llm_comparison_score(
        self, response: str, all_responses: dict[str, str], use_embeddings: bool = False
    ) -> int:
        """Calculate score by comparing response against multiple LLM responses (0-10).
        
        Uses word-based similarity (Jaccard) by default, optionally enhanced with embeddings.
        Higher score = higher consensus with other LLMs (less hallucination).
        
        Args:
            response: The response text to evaluate
            all_responses: Dictionary of all LLM responses for comparison
            use_embeddings: Whether to use semantic embeddings for better comparison (default: False)
        """
        if len(all_responses) <= 1:
            # Only one response available, can't compare
            return 6
        
        similarities = []
        
        # Method 1: Word-based Jaccard similarity (fast, deterministic)
        response_words = set(response.lower().split())
        response_words = {w for w in response_words if len(w) > 2}  # Filter short words
        
        for other_response in all_responses.values():
            if other_response == response:
                continue
            
            other_words = set(other_response.lower().split())
            other_words = {w for w in other_words if len(w) > 2}
            
            if response_words and other_words:
                # Jaccard similarity
                intersection = len(response_words & other_words)
                union = len(response_words | other_words)
                similarity = intersection / union if union > 0 else 0
                similarities.append(similarity)
        
        if not similarities:
            return 6
        
        # Calculate average similarity
        avg_similarity = sum(similarities) / len(similarities)
        
        # Optional: Use embeddings for semantic similarity (better but slower)
        if use_embeddings:
            try:
                from app.services.embedding.embedding_service import EmbeddingService
                from app.services.embedding.similarity_service import SimilarityService
                
                embedding_service = EmbeddingService()
                similarity_service = SimilarityService()
                
                # Generate embeddings
                response_embedding = await embedding_service.generate_embedding(response)
                semantic_similarities = []
                
                for other_response in all_responses.values():
                    if other_response == response:
                        continue
                    
                    other_embedding = await embedding_service.generate_embedding(other_response)
                    semantic_sim = similarity_service.cosine_similarity(
                        response_embedding, other_embedding
                    )
                    semantic_similarities.append(max(0, semantic_sim))  # Ensure non-negative
                
                if semantic_similarities:
                    avg_semantic_sim = sum(semantic_similarities) / len(semantic_similarities)
                    # Blend word-based and semantic similarity (40% word, 60% semantic)
                    avg_similarity = avg_similarity * 0.4 + avg_semantic_sim * 0.6
            except Exception:
                pass  # Fall back to word-based similarity
        
        # Convert similarity (0-1) to score (0-10)
        # Higher similarity = higher score (more consensus = less hallucination)
        score = int(avg_similarity * 10)
        return max(0, min(10, score))

