"""Security utilities for authentication."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    try:
        # Use bcrypt directly to avoid passlib initialization issues
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password.
    
    Bcrypt has a 72 byte limit for passwords. This function ensures
    passwords are properly truncated if they exceed this limit.
    """
    # Ensure password is a string and encode to bytes
    password_str = str(password)
    password_bytes = password_str.encode('utf-8')
    
    # Bcrypt has a 72 byte limit, truncate if necessary
    if len(password_bytes) > 72:
        # Truncate to 72 bytes, ensuring we don't break UTF-8 encoding
        truncated = password_bytes[:72]
        # Remove any incomplete UTF-8 sequences at the end
        while truncated and (truncated[-1] & 0xC0) == 0x80:
            truncated = truncated[:-1]
        password_bytes = truncated
    
    # Generate salt and hash using bcrypt directly
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    jwt_settings = settings.jwt
    
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=jwt_settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, jwt_settings.secret_key, algorithm=jwt_settings.algorithm)
    return encoded_jwt


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a JWT refresh token."""
    settings = get_settings()
    jwt_settings = settings.jwt
    
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=jwt_settings.refresh_token_expire_days)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, jwt_settings.secret_key, algorithm=jwt_settings.algorithm)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and verify a JWT token."""
    settings = get_settings()
    jwt_settings = settings.jwt
    
    try:
        payload = jwt.decode(token, jwt_settings.secret_key, algorithms=[jwt_settings.algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        # Token has expired
        return None
    except jwt.JWTError:
        # Invalid token, signature, or other JWT error
        return None

