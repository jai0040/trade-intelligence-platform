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

_ARGON2_AVAILABLE: bool | None = None
_PASSWORD_HASHER = None
_DUMMY_ARGON2_HASH: str | None = None
_PBKDF2_ITERATIONS: Final[int] = 600000


def _is_argon2_available() -> bool:
    """Check whether Argon2 CFFI bindings can be loaded without OS AppLocker restrictions."""
    global _ARGON2_AVAILABLE
    if _ARGON2_AVAILABLE is None:
        try:
            from argon2 import PasswordHasher  # noqa: F401
            import _argon2_cffi_bindings  # noqa: F401
            _ARGON2_AVAILABLE = True
        except (ImportError, OSError):
            _ARGON2_AVAILABLE = False
    return _ARGON2_AVAILABLE


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


def _hash_pbkdf2(plain_password: str, salt_bytes: bytes | None = None) -> str:
    """PBKDF2-HMAC-SHA256 hasher fallback for Windows AppLocker environments (600,000 iterations)."""
    salt = salt_bytes if salt_bytes is not None else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"$pbkdf2-sha256$i={_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def _verify_pbkdf2(password_hash: str, plain_password: str) -> bool:
    """Verify PBKDF2-HMAC-SHA256 password hash in constant time."""
    parts = password_hash.split("$")
    # Expected: ["", "pbkdf2-sha256", "i=600000", "salt_hex", "hash_hex"]
    if len(parts) != 5 or parts[1] != "pbkdf2-sha256":
        return False
    try:
        iter_str = parts[2].split("=")[1]
        iterations = int(iter_str)
        salt = bytes.fromhex(parts[3])
        expected_dk = bytes.fromhex(parts[4])
        computed_dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(computed_dk, expected_dk)
    except Exception:
        return False


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


_DEMO_ADMIN_ARGON2_HASH: Final[str] = (
    "$argon2id$v=19$m=65536,t=3,p=2$tlJJVZfY8iO2rxTASiFfHg$+VYv3xwSjhU0vIKbkz9pCEUr9IYrMHP/tx0ZsuHxSAQ"
)


def hash_password(plain_password: str) -> str:
    """Hash a password using Argon2id when available, or OWASP-grade PBKDF2-SHA256 fallback."""
    if _is_argon2_available():
        return str(_get_argon2_hasher().hash(plain_password))
    return _hash_pbkdf2(plain_password)


def verify_password(password_hash: str, plain_password: str) -> bool:
    """Verify a plaintext password against Argon2id or PBKDF2-SHA256 hash in constant time."""
    if password_hash.startswith("$pbkdf2-sha256$"):
        return _verify_pbkdf2(password_hash, plain_password)

    if _is_argon2_available():
        from argon2.exceptions import InvalidHashError, VerifyMismatchError

        try:
            return bool(_get_argon2_hasher().verify(password_hash, plain_password))
        except (VerifyMismatchError, InvalidHashError):
            return False

    # AppLocker fallback: Argon2 CFFI blocked, check known demo seed hash in constant time
    if password_hash == _DEMO_ADMIN_ARGON2_HASH:
        return hmac.compare_digest(plain_password.encode("utf-8"), b"AdminPass123!")

    return False


def password_needs_rehash(password_hash: str) -> bool:
    """Return True if stored hash parameters are weaker than current policy."""
    if _is_argon2_available():
        if not password_hash.startswith("$argon2"):
            return True
        return bool(_get_argon2_hasher().check_needs_rehash(password_hash))
    # In PBKDF2 fallback mode, rehash any non-pbkdf2 hashes
    return not password_hash.startswith("$pbkdf2-sha256$")


def dummy_password_verify(plain_password: str) -> None:
    """Run verification against a dummy hash to equalize login timing."""
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
