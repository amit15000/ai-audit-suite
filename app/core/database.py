"""Database setup and session management."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

# Create declarative base for ORM models
Base = declarative_base()

# Global session factory (will be initialized on first use)
SessionLocal: sessionmaker | None = None


def get_engine():
    """Get or create the database engine."""
    settings = get_settings().database
    return create_engine(
        settings.url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        echo=False,
        future=True,
    )


def get_session_factory():
    """Get or create the session factory."""
    global SessionLocal
    if SessionLocal is None:
        engine = get_engine()
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal


def get_db():
    """Dependency for getting a database session."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    # Import models to ensure they're registered with Base.metadata
    from app.domain import models  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)

