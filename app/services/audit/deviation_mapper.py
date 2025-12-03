"""Service for creating deviation maps showing where LLMs differ."""
from __future__ import annotations

import difflib
import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class DeviationMapper:
    """Creates visual maps showing where and how LLMs differ."""

    def create_deviation_map(
        self,
        responses: dict[str, str],
    ) -> dict[str, Any]:
        """Create a deviation map showing differences between LLM responses.
        
        Args:
            responses: Dictionary mapping provider_id to response text
            
        Returns:
            Dictionary with deviation map data including:
            - sentence_comparisons: Sentence-level alignment with word-level diffs
            - conflict_areas: Color-coded conflict zones (red/yellow/green)
            - visual_map: B2B-ready visual data structure
            - side_by_side: Side-by-side comparison views
            - deviation_score: Overall agreement score (0-1)
        """
        if len(responses) < 2:
            return {
                "sentence_comparisons": [],
                "conflict_areas": [],
                "visual_map": {},
                "side_by_side": [],
                "deviation_score": 0.0,
                "explanation": "Insufficient responses for deviation mapping (need at least 2)"
            }
        
        # 1. Sentence-level comparison with alignment
        sentence_comparisons = self._compare_sentences_advanced(responses)
        
        # 2. Word-level highlighting for differences
        highlighted_comparisons = self._add_word_level_highlights(sentence_comparisons, responses)
        
        # 3. Identify conflict areas with severity
        conflict_areas = self._identify_conflict_areas_advanced(highlighted_comparisons)
        
        # 4. Create visual map for B2B frontend
        visual_map = self._create_visual_map(highlighted_comparisons, conflict_areas, responses)
        
        # 5. Create side-by-side comparison views
        side_by_side = self._create_side_by_side_views(responses, highlighted_comparisons)
        
        # 6. Calculate overall deviation score
        deviation_score = self._calculate_deviation_score(highlighted_comparisons)
        
        return {
            "sentence_comparisons": highlighted_comparisons,
            "conflict_areas": conflict_areas,
            "visual_map": visual_map,
            "side_by_side": side_by_side,
            "deviation_score": deviation_score,
            "total_responses": len(responses),
            "providers": list(responses.keys()),
            "explanation": self._generate_explanation(deviation_score, len(conflict_areas))
        }

    def _compare_sentences_advanced(
        self, responses: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Compare responses at sentence level with better alignment."""
        # Split responses into sentences with position tracking
        response_sentences = {}
        for provider_id, text in responses.items():
            sentences = self._split_into_sentences(text)
            response_sentences[provider_id] = sentences
        
        # Use sequence matching to align sentences across responses
        all_providers = list(responses.keys())
        if len(all_providers) < 2:
            return []
        
        # Create alignment matrix
        comparisons = []
        
        # Get reference response (longest one for better alignment)
        reference_provider = max(all_providers, key=lambda p: len(responses[p]))
        reference_sentences = response_sentences[reference_provider]
        
        # For each sentence in reference, find matches in other responses
        for ref_idx, ref_sentence in enumerate(reference_sentences):
            sentence_data = {
                "sentence_index": ref_idx,
                "reference_sentence": ref_sentence,
                "providers": {},
                "alignment": {}
            }
            
            # Check each provider's response
            for provider_id in all_providers:
                provider_sentences = response_sentences[provider_id]
                
                # Find best matching sentence
                best_match_idx = -1
                best_similarity = 0.0
                best_sentence = None
                
                for idx, sentence in enumerate(provider_sentences):
                    similarity = self._sentence_similarity(ref_sentence, sentence)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match_idx = idx
                        best_sentence = sentence
                
                sentence_data["providers"][provider_id] = {
                    "sentence": best_sentence if best_sentence else "",
                    "sentence_index": best_match_idx,
                    "similarity": best_similarity,
                    "has_sentence": best_similarity >= 0.7
                }
            
            # Calculate agreement level
            providers_with = [
                p for p, data in sentence_data["providers"].items()
                if data["has_sentence"]
            ]
            agreement_level = len(providers_with) / len(all_providers)
            
            sentence_data["agreement_level"] = agreement_level
            sentence_data["providers_with"] = providers_with
            sentence_data["providers_without"] = [p for p in all_providers if p not in providers_with]
            sentence_data["type"] = "common" if agreement_level >= 0.9 else "difference"
            
            comparisons.append(sentence_data)
        
        return comparisons

    def _add_word_level_highlights(
        self, 
        sentence_comparisons: list[dict[str, Any]], 
        responses: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Add word-level highlighting to sentence comparisons."""
        highlighted = []
        
        for comp in sentence_comparisons:
            highlighted_comp = comp.copy()
            highlighted_comp["word_diffs"] = {}
            
            # Get reference sentence
            ref_sentence = comp.get("reference_sentence", "")
            if not ref_sentence:
                highlighted.append(highlighted_comp)
                continue
            
            # Compare each provider's sentence with reference
            for provider_id, provider_data in comp["providers"].items():
                provider_sentence = provider_data.get("sentence", "")
                if not provider_sentence or provider_sentence == ref_sentence:
                    continue
                
                # Create word-level diff
                word_diff = self._create_word_level_diff(ref_sentence, provider_sentence)
                highlighted_comp["word_diffs"][provider_id] = word_diff
            
            highlighted.append(highlighted_comp)
        
        return highlighted

    def _create_word_level_diff(self, text1: str, text2: str) -> dict[str, Any]:
        """Create word-level diff with highlighting information."""
        words1 = text1.split()
        words2 = text2.split()
        
        # Use difflib to find differences
        matcher = difflib.SequenceMatcher(None, words1, words2)
        
        # Extract changes
        additions = []  # Words in text2 but not in text1
        deletions = []  # Words in text1 but not in text2
        matches = []   # Matching words
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                matches.extend(words1[i1:i2])
            elif tag == 'delete':
                deletions.extend(words1[i1:i2])
            elif tag == 'insert':
                additions.extend(words2[j1:j2])
            elif tag == 'replace':
                deletions.extend(words1[i1:i2])
                additions.extend(words2[j1:j2])
        
        return {
            "additions": additions,
            "deletions": deletions,
            "matches": matches,
            "similarity": matcher.ratio(),
            "total_changes": len(additions) + len(deletions),
            "change_percentage": (len(additions) + len(deletions)) / max(len(words1), len(words2), 1) * 100
        }

    def _identify_conflict_areas_advanced(
        self, sentence_comparisons: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Identify conflict areas with severity levels and color coding."""
        conflict_areas = []
        
        for comp in sentence_comparisons:
            if comp["type"] == "common":
                continue
            
            agreement = comp["agreement_level"]
            severity = None
            color = None
            color_code = None
            
            if agreement < 0.3:
                severity = "critical"
                color = "red"
                color_code = "#dc3545"  # Bootstrap red
            elif agreement < 0.5:
                severity = "high"
                color = "orange"
                color_code = "#fd7e14"  # Bootstrap orange
            elif agreement < 0.7:
                severity = "medium"
                color = "yellow"
                color_code = "#ffc107"  # Bootstrap yellow
            elif agreement < 0.9:
                severity = "low"
                color = "light-yellow"
                color_code = "#fff3cd"  # Light yellow
            else:
                continue  # Skip if agreement is high enough
            
            # Calculate conflict intensity
            providers_with = comp.get("providers_with", [])
            providers_without = comp.get("providers_without", [])
            
            conflict_area = {
                "sentence_index": comp.get("sentence_index", 0),
                "sentence": comp.get("reference_sentence", "")[:200],
                "severity": severity,
                "color": color,
                "color_code": color_code,
                "agreement_level": agreement,
                "providers_agreeing": providers_with,
                "providers_disagreeing": providers_without,
                "conflict_intensity": 1.0 - agreement,
                "word_diffs": comp.get("word_diffs", {})
            }
            
            conflict_areas.append(conflict_area)
        
        # Sort by severity (critical first)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        conflict_areas.sort(key=lambda x: severity_order.get(x["severity"], 4))
        
        return conflict_areas

    def _create_visual_map(
        self,
        sentence_comparisons: list[dict[str, Any]],
        conflict_areas: list[dict[str, Any]],
        responses: dict[str, str]
    ) -> dict[str, Any]:
        """Create B2B-ready visual map data structure."""
        providers = list(responses.keys())
        
        # Create visual segments
        segments = []
        for comp in sentence_comparisons:
            segment = {
                "index": comp.get("sentence_index", 0),
                "sentence": comp.get("reference_sentence", "")[:200],
                "status": "agreement" if comp["type"] == "common" else "conflict",
                "agreement_level": comp["agreement_level"],
                "providers": {}
            }
            
            # Add provider-specific data
            for provider_id in providers:
                provider_data = comp["providers"].get(provider_id, {})
                segment["providers"][provider_id] = {
                    "has_sentence": provider_data.get("has_sentence", False),
                    "similarity": provider_data.get("similarity", 0.0),
                    "sentence": provider_data.get("sentence", "")[:200]
                }
            
            segments.append(segment)
        
        # Create conflict summary
        conflict_summary = {
            "total_conflicts": len(conflict_areas),
            "critical": len([c for c in conflict_areas if c["severity"] == "critical"]),
            "high": len([c for c in conflict_areas if c["severity"] == "high"]),
            "medium": len([c for c in conflict_areas if c["severity"] == "medium"]),
            "low": len([c for c in conflict_areas if c["severity"] == "low"])
        }
        
        # Create color map for visualization
        color_map = {
            "agreement": {"color": "green", "code": "#28a745"},
            "critical": {"color": "red", "code": "#dc3545"},
            "high": {"color": "orange", "code": "#fd7e14"},
            "medium": {"color": "yellow", "code": "#ffc107"},
            "low": {"color": "light-yellow", "code": "#fff3cd"}
        }
        
        return {
            "segments": segments,
            "conflict_summary": conflict_summary,
            "color_map": color_map,
            "total_segments": len(segments),
            "providers": providers
        }

    def _create_side_by_side_views(
        self,
        responses: dict[str, str],
        sentence_comparisons: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Create side-by-side comparison views for each provider pair."""
        providers = list(responses.keys())
        side_by_side = []
        
        # Create pairwise comparisons
        for i, provider1 in enumerate(providers):
            for provider2 in providers[i+1:]:
                comparison = {
                    "provider1": provider1,
                    "provider2": provider2,
                    "sentences": []
                }
                
                # Align sentences for this pair
                for comp in sentence_comparisons:
                    p1_data = comp["providers"].get(provider1, {})
                    p2_data = comp["providers"].get(provider2, {})
                    
                    sentence_pair = {
                        "index": comp.get("sentence_index", 0),
                        "provider1_sentence": p1_data.get("sentence", ""),
                        "provider2_sentence": p2_data.get("sentence", ""),
                        "similarity": self._sentence_similarity(
                            p1_data.get("sentence", ""),
                            p2_data.get("sentence", "")
                        ),
                        "status": "match" if p1_data.get("has_sentence") and p2_data.get("has_sentence") and 
                                  self._sentence_similarity(p1_data.get("sentence", ""), p2_data.get("sentence", "")) >= 0.7
                                  else "diff",
                        "word_diff": comp.get("word_diffs", {}).get(provider2, {})
                    }
                    
                    comparison["sentences"].append(sentence_pair)
                
                side_by_side.append(comparison)
        
        return side_by_side

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences with better handling."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Split on sentence endings
        sentences = re.split(r'([.!?]+(?:\s+|$))', text)
        
        # Recombine sentences with their punctuation
        result = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                sentence = (sentences[i] + sentences[i + 1]).strip()
            else:
                sentence = sentences[i].strip()
            
            if sentence and len(sentence) > 10:
                result.append(sentence)
        
        # If no sentences found, return the whole text as one sentence
        if not result:
            result = [text] if text else []
        
        return result

    def _sentence_similarity(self, sentence1: str, sentence2: str) -> float:
        """Calculate similarity between two sentences."""
        if not sentence1 or not sentence2:
            return 0.0
        
        # Normalize sentences
        s1 = sentence1.lower().strip()
        s2 = sentence2.lower().strip()
        
        if s1 == s2:
            return 1.0
        
        # Use SequenceMatcher for similarity
        similarity = difflib.SequenceMatcher(None, s1, s2).ratio()
        
        # Also check word-level similarity
        words1 = set(s1.split())
        words2 = set(s2.split())
        
        if not words1 or not words2:
            return similarity
        
        # Jaccard similarity for word sets
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        word_similarity = intersection / union if union > 0 else 0.0
        
        # Combine both similarities
        combined = (similarity * 0.6) + (word_similarity * 0.4)
        
        return combined

    def _calculate_deviation_score(
        self, sentence_comparisons: list[dict[str, Any]]
    ) -> float:
        """Calculate overall deviation score (0-1, where 1 = complete agreement)."""
        if not sentence_comparisons:
            return 1.0
        
        # Weighted average agreement level
        total_weight = 0
        weighted_sum = 0.0
        
        for comp in sentence_comparisons:
            # Weight by sentence length (longer sentences matter more)
            sentence = comp.get("reference_sentence", "")
            weight = len(sentence.split())
            agreement = comp.get("agreement_level", 1.0)
            
            weighted_sum += agreement * weight
            total_weight += weight
        
        if total_weight == 0:
            return 1.0
        
        return weighted_sum / total_weight

    def _generate_explanation(self, deviation_score: float, conflict_count: int) -> str:
        """Generate explanation for the deviation map."""
        if deviation_score >= 0.9:
            base = f"Excellent agreement across responses (deviation score: {deviation_score:.2f})."
        elif deviation_score >= 0.8:
            base = f"High agreement across responses (deviation score: {deviation_score:.2f})."
        elif deviation_score >= 0.6:
            base = f"Moderate agreement across responses (deviation score: {deviation_score:.2f})."
        elif deviation_score >= 0.4:
            base = f"Low agreement across responses (deviation score: {deviation_score:.2f})."
        else:
            base = f"Very low agreement across responses (deviation score: {deviation_score:.2f})."
        
        if conflict_count > 0:
            base += f" Found {conflict_count} conflict area(s) where responses differ significantly."
        else:
            base += " No significant conflicts detected."
        
        return base

    def create_word_level_diff(
        self, text1: str, text2: str, provider1: str, provider2: str
    ) -> dict[str, Any]:
        """Create word-level difference between two responses (legacy method for compatibility)."""
        word_diff = self._create_word_level_diff(text1, text2)
        
        return {
            "provider1": provider1,
            "provider2": provider2,
            "additions": word_diff["additions"][:20],  # Limit to 20
            "deletions": word_diff["deletions"][:20],  # Limit to 20
            "similarity": word_diff["similarity"]
        }
