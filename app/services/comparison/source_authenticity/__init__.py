"""Source authenticity scoring modules."""
from __future__ import annotations

from app.services.comparison.source_authenticity.verifies_papers_exist import VerifiesPapersExistScorer
from app.services.comparison.source_authenticity.detects_fake_citations import DetectsFakeCitationsScorer
from app.services.comparison.source_authenticity.confirms_legal_references import ConfirmsLegalReferencesScorer

__all__ = [
    "VerifiesPapersExistScorer",
    "DetectsFakeCitationsScorer",
    "ConfirmsLegalReferencesScorer",
]

