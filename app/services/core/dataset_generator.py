from __future__ import annotations

from typing import List

from app.services.core.safety_checker import SafetyChecker


class DatasetGenerator:
    """Local rule-based dataset generator enforcing non-actionability."""

    def __init__(self) -> None:
        self._safety = SafetyChecker()

    def generate(self, seed: str, count: int = 3) -> List[str]:
        samples: List[str] = []
        for idx in range(count):
            content = f"[dataset] seed::{seed} example::{idx}"
            safety = self._safety.sanitize(
                adapter_id=f"dataset-{idx}",
                text=content,
                pii_allowed=False,
            )
            samples.append(safety.sanitized_text)
        return samples

