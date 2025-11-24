"""Base repository class."""
from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from app.core.database import get_session_factory

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Base repository class providing common database operations."""

    def __init__(self, session: Session | None = None) -> None:
        """Initialize repository with optional session.

        Args:
            session: Optional database session. If not provided, uses session factory.
        """
        if session:
            self._session = session
            self._own_session = False
        else:
            self._session_factory = get_session_factory()
            self._session = None
            self._own_session = True

    def _get_session(self) -> Session:
        """Get database session."""
        if self._own_session:
            if self._session is None:
                self._session = self._session_factory()
            return self._session
        return self._session

    def close(self) -> None:
        """Close the session if we own it."""
        if self._own_session and self._session:
            self._session.close()
            self._session = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

