"""Authentication API router."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.auth_schemas import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    TokenResponse,
)
from app.domain.models import User
from app.services.core.auth_service import (
    authenticate_user,
    create_tokens_for_user,
    create_user,
    get_user_by_email,
)
from app.utils.dependencies import get_current_user
from app.utils.security import create_access_token, decode_token

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticate user and return JWT tokens",
)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """User login endpoint (DUMMY MODE - accepts any email/password)."""
    try:
        # DUMMY AUTH: Always authenticate successfully
        user = authenticate_user(db, request.email, request.password)
        # authenticate_user now always returns a user (creates if needed)
        
        tokens = create_tokens_for_user(user)
        
        return LoginResponse(
            success=True,
            data={
                "user": {
                    "id": str(user.id),  # type: ignore[arg-type]
                    "email": str(user.email),  # type: ignore[arg-type]
                    "name": user.name,  # type: ignore[arg-type]
                },
                "token": tokens["access_token"],
                "refreshToken": tokens["refresh_token"],
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("auth.login.error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An error occurred during login",
                },
            },
        ) from e


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User registration",
    description="Register a new user account",
)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    """User registration endpoint (DUMMY MODE - allows duplicate emails)."""
    try:
        # DUMMY AUTH: Allow duplicate emails, just get or create user
        existing_user = get_user_by_email(db, request.email)
        if existing_user:
            # If user exists, just return tokens for existing user
            user = existing_user
        else:
            # Create new user
            user = create_user(db, request.email, request.password, request.name)
        
        tokens = create_tokens_for_user(user)
        
        return RegisterResponse(
            success=True,
            data={
                "user": {
                    "id": str(user.id),  # type: ignore[arg-type]
                    "email": str(user.email),  # type: ignore[arg-type]
                    "name": user.name,  # type: ignore[arg-type]
                },
                "token": tokens["access_token"],
                "refreshToken": tokens["refresh_token"],
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("auth.register.error", error=str(e), exc_info=True, error_type=type(e).__name__)
        # Include more details in development
        error_message = str(e)
        if "no such table" in error_message.lower() or "relation" in error_message.lower():
            error_message = "Database tables not initialized. Please run: python scripts/init_db.py"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"An error occurred during registration: {error_message}",
                },
            },
        ) from e


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Get a new access token using a refresh token",
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> RefreshTokenResponse:
    """Refresh access token endpoint (DUMMY MODE - always succeeds)."""
    try:
        # DUMMY AUTH: Try to decode token, but always succeed with dummy user if needed
        payload = decode_token(request.refreshToken)
        user_id: str | None = None
        
        if payload:
            user_id = payload.get("sub")
        
        # Get user from database or create dummy user
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        else:
            user = None
        
        if not user:
            # Create/get default dummy user
            import uuid
            default_email = "dummy@example.com"
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
        
        # Generate new access token (keep the same refresh token)
        user_id_str = str(user.id)  # type: ignore[arg-type]
        new_access_token = create_access_token(data={"sub": user_id_str})
        
        return RefreshTokenResponse(
            success=True,
            data=TokenResponse(
                token=new_access_token,
                refreshToken=request.refreshToken,  # Return the same refresh token
                tokenType="bearer",
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("auth.refresh.error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An error occurred during token refresh",
                },
            },
        ) from e


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Get the currently authenticated user's information",
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> CurrentUserResponse:
    """Get current user information endpoint."""
    try:
        return CurrentUserResponse(
            success=True,
            data={
                "id": str(current_user.id),  # type: ignore[arg-type]
                "email": str(current_user.email),  # type: ignore[arg-type]
                "name": current_user.name,  # type: ignore[arg-type]
                "isActive": bool(current_user.is_active),  # type: ignore[arg-type]
            },
        )
    except Exception as e:
        logger.error("auth.me.error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An error occurred while retrieving user information",
                },
            },
        ) from e

