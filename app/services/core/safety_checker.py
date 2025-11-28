from __future__ import annotations

import re
from typing import Iterable, List

from app.domain.schemas import SafetyFinding, SafetyResult


class SafetyChecker:
    """Rule-based sanitizer enforcing local safety policies."""

    _harmful_patterns = [
        re.compile(r"\b(bomb|explosive|weapon)\b", re.IGNORECASE),
        re.compile(r"\b(hack|exploit)\b", re.IGNORECASE),
    ]

    _pii_patterns = [
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN pattern
        re.compile(r"\b\d{16}\b"),  # credit card placeholder
    ]

    def sanitize(self, adapter_id: str, text: str, pii_allowed: bool) -> SafetyResult:
        findings: List[SafetyFinding] = []
        sanitized = text

        for pattern in self._harmful_patterns:
            sanitized, pattern_findings = self._replace_matches(
                sanitized, pattern, "harmful_content"
            )
            findings.extend(pattern_findings)

        if not pii_allowed:
            for pattern in self._pii_patterns:
                sanitized, pattern_findings = self._replace_matches(
                    sanitized, pattern, "pii_violation"
                )
                findings.extend(pattern_findings)

        return SafetyResult(
            adapter_id=adapter_id,
            sanitized_text=sanitized,
            findings=findings,
        )

    def _replace_matches(
        self, text: str, pattern: re.Pattern[str], category: str
    ) -> tuple[str, List[SafetyFinding]]:
        findings: List[SafetyFinding] = []
        matches: Iterable[re.Match[str]] = list(pattern.finditer(text))
        sanitized = text
        for match in matches:
            span = match.group(0)
            sanitized = sanitized.replace(span, "[REDACTED_HARMFUL_CONTENT]")
            findings.append(
                SafetyFinding(category=category, details=f"Matched pattern: {pattern}")
            )
        return sanitized, findings

