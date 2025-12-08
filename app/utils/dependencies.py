"""FastAPI dependencies for authentication."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.models import User
from app.utils.security import decode_token

# Use HTTPBearer instead of OAuth2PasswordBearer - simpler Bearer token auth
# This will show a simple "Bearer" token input in Swagger UI (no OAuth2 flow)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user (DUMMY MODE - always returns dummy user, no token required)."""
    # DUMMY AUTH: Always return a dummy user, ignore token validation
    # Works even without token - perfect for development/testing
    import uuid
    
    # Try to extract user_id from token if provided, otherwise use default
    user_id = None
    if credentials and credentials.credentials:
        try:
            payload = decode_token(credentials.credentials)
            if payload:
                user_id = payload.get("sub")
        except Exception:
            pass  # Ignore token errors in dummy mode
    
    # If we have a user_id from token, try to get that user
    if user_id:
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return user
        except Exception:
            pass  # Ignore DB errors, fall through to create dummy user
    
    # Otherwise, get or create a default dummy user
    default_email = "dummy@example.com"
    try:
        user = db.query(User).filter(User.email == default_email).first()
        if not user:
            user = User(
                id=f"user_{uuid.uuid4().hex[:12]}",
                email=default_email,
                hashed_password="dummy_hash",
                name="Dummy User",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    except Exception:
        # If DB fails, create a minimal user object (won't persist but will work for API)
        return User(
            id=f"user_{uuid.uuid4().hex[:12]}",
            email=default_email,
            hashed_password="dummy_hash",
            name="Dummy User",
            is_active=True,
        )

