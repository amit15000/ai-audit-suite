"""AI plagiarism scoring modules."""
from __future__ import annotations

from app.services.comparison.ai_plagiarism.copied_sentences import CopiedSentencesScorer
from app.services.comparison.ai_plagiarism.copied_news_articles import CopiedNewsArticlesScorer
from app.services.comparison.ai_plagiarism.copied_books import CopiedBooksScorer
from app.services.comparison.ai_plagiarism.copied_copyrighted_text import CopiedCopyrightedTextScorer

__all__ = [
    "CopiedSentencesScorer",
    "CopiedNewsArticlesScorer",
    "CopiedBooksScorer",
    "CopiedCopyrightedTextScorer",
]

