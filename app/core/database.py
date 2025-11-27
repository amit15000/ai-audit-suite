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
    # Convert postgresql:// URLs to use psycopg3 (psycopg) instead of psycopg2
    db_url = settings.url
    if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
        # Replace postgresql:// or postgres:// with postgresql+psycopg://
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    
    return create_engine(
        db_url,
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

    try:
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.warning("database.init_failed", error=str(e), message="Database initialization failed, will retry on first use")
        # Re-raise only if it's not a connection error (e.g., SQLite should always work)
        # For PostgreSQL connection errors, we'll allow the app to start and retry later
        if "connection" in str(e).lower() or "operational" in str(e).lower():
            logger.info("database.connection_error_ignored", message="Connection error ignored, database will be initialized on first use")
            return
        raise

