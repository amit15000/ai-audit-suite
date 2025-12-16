"""Compliance scoring modules."""
from __future__ import annotations

from app.services.comparison.compliance.checks_urls_exist import ChecksUrlsExistScorer
from app.services.comparison.compliance.verifies_papers_exist import VerifiesPapersExistScorer
from app.services.comparison.compliance.detects_fake_citations import DetectsFakeCitationsScorer
from app.services.comparison.compliance.confirms_legal_references import ConfirmsLegalReferencesScorer

__all__ = [
    "ChecksUrlsExistScorer",
    "VerifiesPapersExistScorer",
    "DetectsFakeCitationsScorer",
    "ConfirmsLegalReferencesScorer",
]

