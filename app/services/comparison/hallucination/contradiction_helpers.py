"""Helper functions for detecting contradictions in text."""
from __future__ import annotations

import re


def extract_factual_claims(sentences: list[str]) -> list[dict]:
    """Extract factual claims from sentences.
    
    Args:
        sentences: List of sentences to analyze
        
    Returns:
        List of claims with subject, value, and sentence index
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


def detect_claim_contradictions(claims: list[dict]) -> float:
    """Detect contradictions in factual claims.
    
    Args:
        claims: List of claim dictionaries
        
    Returns:
        Score indicating number of contradictions found
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
                value_list = list(unique_values)
                for i, val1 in enumerate(value_list):
                    for val2 in value_list[i+1:]:
                        if are_opposite_values(val1, val2):
                            contradiction_count += 0.5
    
    return contradiction_count


def are_opposite_values(val1: str, val2: str) -> bool:
    """Check if two values are semantically opposite.
    
    Args:
        val1: First value to compare
        val2: Second value to compare
        
    Returns:
        True if values are opposite, False otherwise
    """
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


def has_negation_relationship(sent1: str, sent2: str) -> bool:
    """Check if two sentences have a negation relationship.
    
    Args:
        sent1: First sentence
        sent2: Second sentence
        
    Returns:
        True if sentences have negation relationship, False otherwise
    """
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


def detect_semantic_contradictions(
    sentence_embeddings: list[tuple[str, list[float]]],
    similarity_service
) -> float:
    """Detect semantic contradictions using embeddings.
    
    Compares sentence embeddings to find semantically opposite statements.
    
    Args:
        sentence_embeddings: List of (sentence, embedding) tuples
        similarity_service: Service for calculating similarity
        
    Returns:
        Contradiction score
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
                    if has_negation_relationship(sent1, sent2):
                        contradiction_count += 0.5
    
    return contradiction_count


def detect_explicit_contradictions(sentences: list[str]) -> float:
    """Detect explicit contradictions using pattern matching.
    
    Looks for clear contradiction patterns like "X is Y, but X is not Y".
    
    Args:
        sentences: List of sentences to analyze
        
    Returns:
        Contradiction score
    """
    contradiction_count = 0.0
    
    # Pattern: "X is Y" followed by "X is not Y" or "X is Z" (where Z contradicts Y)
    for i, sent1 in enumerate(sentences):
        for sent2 in sentences[i+1:]:
            # Extract subjects and predicates
            sent1_claims = re.findall(
                r'(\w+(?:\s+\w+)*?)\s+(?:is|are|was|were)\s+([^.]+)', sent1, re.IGNORECASE
            )
            sent2_claims = re.findall(
                r'(\w+(?:\s+\w+)*?)\s+(?:is|are|was|were)\s+([^.]+)', sent2, re.IGNORECASE
            )
            
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
                        elif are_opposite_values(pred1_lower, pred2_lower):
                            contradiction_count += 0.5
    
    return contradiction_count

