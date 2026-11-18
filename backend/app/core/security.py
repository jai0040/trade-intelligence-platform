"""Cryptographic helpers: Argon2id password hashing, opaque tokens, SHA-256 hashing, and CSRF."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Final

EMAIL_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)
PASSWORD_MIN_LENGTH: Final[int] = 10
PASSWORD_MAX_LENGTH: Final[int] = 128

_PASSWORD_HASHER = None
_DUMMY_ARGON2_HASH: str | None = None


def _get_argon2_hasher():
    """Return configured Argon2id PasswordHasher (time_cost=3, memory=64 MiB, parallelism=2)."""
    global _PASSWORD_HASHER
    if _PASSWORD_HASHER is None:
        from argon2 import PasswordHasher, Type

        _PASSWORD_HASHER = PasswordHasher(
            time_cost=3,
            memory_cost=65536,  # 64 MiB
            parallelism=2,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
    return _PASSWORD_HASHER


def normalize_email(raw_email: str) -> str:
    """Validate and canonicalize email addresses (lowercase, trimmed)."""
    cleaned = raw_email.strip().lower()
    if not cleaned or len(cleaned) > 254 or not EMAIL_REGEX.match(cleaned):
        raise ValueError("Invalid email address format.")
    return cleaned


def validate_password_strength(password: str) -> str:
    """Enforce commercial SaaS password complexity and DoS length bounds."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must not exceed {PASSWORD_MAX_LENGTH} characters.")
    if not any(ch.isupper() for ch in password):
        raise ValueError("Password must include at least one uppercase letter.")
    if not any(ch.islower() for ch in password):
        raise ValueError("Password must include at least one lowercase letter.")
    if not any(ch.isdigit() for ch in password):
        raise ValueError("Password must include at least one digit.")
    if not any(not ch.isalnum() for ch in password):
        raise ValueError("Password must include at least one special character.")
    return password


def hash_password(plain_password: str) -> str:
    """Hash a password using Argon2id."""
    return str(_get_argon2_hasher().hash(plain_password))


def verify_password(password_hash: str, plain_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash in constant time."""
    from argon2.exceptions import InvalidHashError, VerifyMismatchError

    try:
        return bool(_get_argon2_hasher().verify(password_hash, plain_password))
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """Return True if stored hash parameters are weaker than current policy."""
    return bool(_get_argon2_hasher().check_needs_rehash(password_hash))


def dummy_password_verify(plain_password: str) -> None:
    """Run an Argon2id verification against a dummy hash to equalize login timing."""
    global _DUMMY_ARGON2_HASH
    if _DUMMY_ARGON2_HASH is None:
        _DUMMY_ARGON2_HASH = hash_password("DummyTimingGuard!2026#")
    verify_password(_DUMMY_ARGON2_HASH, plain_password)


def generate_opaque_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure 256-bit (default) URL-safe opaque token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """Return the lowercase SHA-256 hex digest of an opaque session or reset token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def constant_time_equals(left: str | None, right: str | None) -> bool:
    """Constant-time string comparison safe against timing side channels."""
    if not left or not right:
        return False
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
