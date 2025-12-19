"""Service for generating embeddings from text using configured embedding model."""
from __future__ import annotations

import asyncio
import structlog
from typing import List

from app.core.config import get_settings
from openai import OpenAI

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Service for generating embeddings from text."""

    def __init__(self) -> None:
        """Initialize the embedding service with configuration."""
        self.settings = get_settings()
        self.model_name = self.settings.embedding.model_name
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            api_key = self.settings.adapter.openai_api_key
            if not api_key:
                # Try to get it directly from environment as fallback
                import os
                api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ADAPTER_OPENAI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "OpenAI API key not configured. Set OPENAI_API_KEY or ADAPTER_OPENAI_API_KEY environment variable."
                    )
            self._client = OpenAI(api_key=api_key)
        return self._client

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: The text to generate embedding for

        Returns:
            List of float values representing the embedding vector

        Raises:
            ValueError: If text is empty
            Exception: If embedding generation fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            logger.debug(
                "embedding.generate_start",
                model=self.model_name,
                text_length=len(text),
            )

            # Run synchronous OpenAI API call in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.embeddings.create(
                    model=self.model_name,
                    input=text,
                )
            )

            embedding = response.data[0].embedding

            logger.debug(
                "embedding.generate_complete",
                model=self.model_name,
                embedding_dim=len(embedding),
            )

            return embedding

        except Exception as e:
            logger.error(
                "embedding.generate_error",
                model=self.model_name,
                error=str(e),
            )
            raise

    async def generate_embeddings_batch(
        self, texts: List[str]
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to generate embeddings for

        Returns:
            List of embedding vectors (each is a list of floats)

        Raises:
            ValueError: If texts list is empty
            Exception: If embedding generation fails
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")

        try:
            logger.debug(
                "embedding.batch_generate_start",
                model=self.model_name,
                batch_size=len(texts),
            )

            # Filter out empty texts
            valid_texts = [text for text in texts if text and text.strip()]
            if not valid_texts:
                raise ValueError("No valid texts to embed")

            # Run synchronous OpenAI API call in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.embeddings.create(
                    model=self.model_name,
                    input=valid_texts,
                )
            )

            embeddings = [item.embedding for item in response.data]

            logger.debug(
                "embedding.batch_generate_complete",
                model=self.model_name,
                embeddings_count=len(embeddings),
            )

            return embeddings

        except Exception as e:
            logger.error(
                "embedding.batch_generate_error",
                model=self.model_name,
                error=str(e),
            )
            raise

