"""Strict Pydantic v2 schemas for authentication, session management, and user profile."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.security import normalize_email, validate_password_strength


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=10, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=120)
    country_code: Literal["IN", "US", "GB", "SG", "AE", "CA", "AU", "OTHER"] = "IN"

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("full_name")
    @classmethod
    def check_full_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return cleaned


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return normalize_email(value)


class PasswordResetRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return normalize_email(value)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=256)
    new_password: str = Field(..., min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    country_code: str
    is_active: bool
    is_email_verified: bool
    subscription_status: str
    entitled_markets: list[str]
    last_login_at: datetime | None = None


class MessageResponse(BaseModel):
    message: str
