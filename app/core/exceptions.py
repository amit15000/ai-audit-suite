"""Custom exception classes for the application."""
from __future__ import annotations


class BaseAppException(Exception):
    """Base exception class for all application exceptions."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(BaseAppException):
    """Raised when validation fails."""

    pass


class NotFoundError(BaseAppException):
    """Raised when a requested resource is not found."""

    pass


class AdapterError(BaseAppException):
    """Raised when adapter execution fails."""

    pass


class JudgeError(BaseAppException):
    """Raised when judge scoring fails."""

    pass


class MultiLLMError(BaseAppException):
    """Raised when multi-LLM collection fails."""

    pass

