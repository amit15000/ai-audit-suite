"""Shared utilities for source authenticity scoring."""
from __future__ import annotations

from app.services.comparison.utils import JUDGE_SYSTEM_PROMPT, extract_json_bool

__all__ = [
    "JUDGE_SYSTEM_PROMPT",
    "extract_json_bool",
]

