"""Accuracy scoring modules."""
from __future__ import annotations

from app.services.comparison.accuracy.google_bing_wikipedia import GoogleBingWikipediaScorer
from app.services.comparison.accuracy.verified_databases import VerifiedDatabasesScorer
from app.services.comparison.accuracy.internal_company_docs import InternalCompanyDocsScorer

__all__ = [
    "GoogleBingWikipediaScorer",
    "VerifiedDatabasesScorer",
    "InternalCompanyDocsScorer",
]

