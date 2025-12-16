"""Service for calculating AI output plagiarism checker scores and sub-scores."""
from __future__ import annotations

from app.domain.schemas import AIPlagiarismSubScore
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.ai_plagiarism import (
    CopiedSentencesScorer,
    CopiedNewsArticlesScorer,
    CopiedBooksScorer,
    CopiedCopyrightedTextScorer,
)


class AIPlagiarismScorer:
    """Service for calculating AI output plagiarism checker scores and sub-scores."""

    def __init__(self):
        """Initialize AI plagiarism scorer with sub-score calculators."""
        self.ai_service = AIPlatformService()
        
        # Initialize sub-score calculators
        self.copied_sentences_scorer = CopiedSentencesScorer(self.ai_service)
        self.copied_news_articles_scorer = CopiedNewsArticlesScorer(self.ai_service)
        self.copied_books_scorer = CopiedBooksScorer(self.ai_service)
        self.copied_copyrighted_text_scorer = CopiedCopyrightedTextScorer(self.ai_service)

    async def calculate_sub_scores(
        self,
        response: str,
        judge_platform_id: str,
        use_llm: bool = False,
    ) -> AIPlagiarismSubScore:
        """Calculate the 4 AI plagiarism sub-scores.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
        
        Returns:
            AIPlagiarismSubScore with percentages (0-100) for:
            - copiedSentences: Copied sentences percentage
            - copiedNewsArticles: Copied news articles percentage
            - copiedBooks: Copied books percentage
            - copiedCopyrightedText: Copied copyrighted text percentage
        """
        copied_sentences = await self.copied_sentences_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        copied_news = await self.copied_news_articles_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        copied_books = await self.copied_books_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        copied_copyrighted = await self.copied_copyrighted_text_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )
        
        return AIPlagiarismSubScore(
            copiedSentences=copied_sentences,
            copiedNewsArticles=copied_news,
            copiedBooks=copied_books,
            copiedCopyrightedText=copied_copyrighted,
        )

    # Legacy method names for backward compatibility
    async def calculate_copied_sentences(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied sentences percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Copied sentences percentage (0-100)
        """
        return await self.copied_sentences_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_copied_news_articles(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied news articles percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Copied news articles percentage (0-100)
        """
        return await self.copied_news_articles_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_copied_books(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied books percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Copied books percentage (0-100)
        """
        return await self.copied_books_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

    async def calculate_copied_copyrighted_text(
        self, response: str, judge_platform_id: str, use_llm: bool = False
    ) -> float:
        """Calculate copied copyrighted text percentage (0-100).
        
        Legacy method for backward compatibility.
        Use calculate_sub_scores() for all sub-scores at once.
        
        Args:
            response: The response text to evaluate
            judge_platform_id: Platform ID for LLM judge (if use_llm=True)
            use_llm: Whether to use LLM for enhanced evaluation (default: False)
            
        Returns:
            Copied copyrighted text percentage (0-100)
        """
        return await self.copied_copyrighted_text_scorer.calculate_score(
            response, judge_platform_id, use_llm=use_llm
        )

