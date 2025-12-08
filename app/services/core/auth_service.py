"""Authentication service."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import User
from app.utils.security import create_access_token, create_refresh_token, get_password_hash, verify_password


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Authenticate a user by email and password (DUMMY MODE - always succeeds)."""
    # DUMMY AUTH: Always return/create user without password verification
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Auto-create user if doesn't exist
        import uuid
        user = User(
            id=f"user_{uuid.uuid4().hex[:12]}",
            email=email,
            hashed_password="dummy_hash",  # Not used in dummy mode
            name=email.split("@")[0],  # Use email prefix as name
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def create_user(db: Session, email: str, password: str, name: str | None = None) -> User:
    """Create a new user (DUMMY MODE - no password hashing)."""
    import uuid
    
    # DUMMY AUTH: Don't hash password, just use dummy value
    user = User(
        id=f"user_{uuid.uuid4().hex[:12]}",
        email=email,
        hashed_password="dummy_hash",  # Not used in dummy mode
        name=name or email.split("@")[0],
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    """Get a user by email."""
    return db.query(User).filter(User.email == email).first()


def create_tokens_for_user(user: User) -> dict[str, str]:
    """Create access and refresh tokens for a user."""
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

