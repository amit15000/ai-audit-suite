from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Tuple

from app.models import JudgmentScores


class JudgeError(Exception):
    """Raised when judge scoring fails."""


@dataclass
class JudgeResult:
    payload: JudgmentScores
    raw_text: str
    fallback_applied: bool


class JudgeEngine:
    """Deterministic rubric enforcement for adapter responses."""

    def score(self, sanitized_text: str) -> JudgeResult:
        raw = self._call_judge_model(sanitized_text)
        parsed, fallback = self._parse_or_fallback(raw)
        return JudgeResult(payload=parsed, raw_text=raw, fallback_applied=fallback)

    def _call_judge_model(self, sanitized_text: str) -> str:
        # Placeholder deterministic scoring for local testing.
        token_count = len(sanitized_text.split())
        base_score = min(10, max(0, token_count // 5))
        rubric = {
            "accuracy": base_score,
            "completeness": base_score,
            "clarity": max(0, base_score - 1),
            "reasoning": base_score,
            "safety": 10,
            "hallucination_risk": max(0, 10 - base_score),
        }
        return json.dumps(rubric)

    def _parse_or_fallback(self, raw: str) -> Tuple[JudgmentScores, bool]:
        try:
            payload = json.loads(raw)
            scores = JudgmentScores(**payload)
            return scores, False
        except Exception:  # noqa: BLE001
            fallback = JudgmentScores(
                accuracy=0,
                completeness=0,
                clarity=0,
                reasoning=0,
                safety=0,
                hallucination_risk=0,
            )
            return fallback, True

