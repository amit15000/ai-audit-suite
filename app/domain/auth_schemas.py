"""Pydantic schemas for authentication."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Schema for login request."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Schema for user registration request."""

    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    name: str | None = Field(None, description="Optional user name")


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refreshToken: str = Field(..., description="Refresh token")


class TokenResponse(BaseModel):
    """Schema for token response."""

    token: str = Field(..., description="Access token")
    refreshToken: str = Field(..., description="Refresh token")
    tokenType: str = Field(default="bearer", description="Token type")


class UserInfo(BaseModel):
    """Schema for user information."""

    id: str
    email: str
    name: str | None
    isActive: bool = Field(..., description="Whether the user account is active")


class LoginResponse(BaseModel):
    """Schema for login response."""

    success: bool
    data: dict


class RegisterResponse(BaseModel):
    """Schema for registration response."""

    success: bool
    data: dict


class RefreshTokenResponse(BaseModel):
    """Schema for refresh token response."""

    success: bool
    data: TokenResponse


class CurrentUserResponse(BaseModel):
    """Schema for current user response."""

    success: bool
    data: UserInfo


class TokenData(BaseModel):
    """Schema for token data."""

    user_id: str | None = None

